"""
Customer Dashboard Views for PharmaHub
Handles customer-specific functionality including cart, symptom checker, and dashboard pages
"""

import json
import os
import pickle
from datetime import datetime
from django.core.mail import send_mail
from django.contrib.auth.models import User
import pandas as pd
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from authentication.decorators import role_required
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from thefuzz import process
import urllib
# customers_d/views.py ke top imports mein add karein
from dashboards.utils import send_pharmacy_notification

# ✅ FIX 1: Sirf ek baar import — duplicate hata diya
from customers_d.models import Cart, CartItem
from dashboards.models import Medicine, Pharmacy
from orders.models import Order, OrderItem

import google.genai as genai

from pages.views import get_base_template

# ==========================
# GEMINI AI CONFIGURATION
# ==========================

genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)
GEMINI_MODEL_NAME = "models/gemini-2.5-flash"

# ==========================
# GLOBAL CONSTANTS & PATHS
# ==========================

BASE_DIR = settings.BASE_DIR
AI_MODEL_DIR = os.path.join(BASE_DIR, "ai_model")
DATASETS_DIR = os.path.join(BASE_DIR, "datasets")

# AI Model Paths
MODEL_PATH = os.path.join(AI_MODEL_DIR, "disease_model.pkl")
FEATURES_PATH = os.path.join(AI_MODEL_DIR, "symptom_features.pkl")
TRAINING_DATA_PATH = os.path.join(AI_MODEL_DIR, "Training.csv")
SYMPTOM_SEVERITY_PATH = os.path.join(AI_MODEL_DIR, "Symptom-severity.csv")

# Dataset Paths
PAK_MEDICINES_PATH = os.path.join(AI_MODEL_DIR, "Pakistan Medicines Dataset.csv")
SYMPTOM_DESCRIPTION_PATH = os.path.join(AI_MODEL_DIR, "symptom_Description.csv")
SYMPTOM_PRECAUTION_PATH = os.path.join(AI_MODEL_DIR, "symptom_precaution.csv")
FORMULA_PATH = os.path.join(AI_MODEL_DIR, "disease_to_formula.csv")

# Dangerous Diseases List
DANGEROUS_DISEASES = [
    'Heart attack', 'Typhoid', 'Malaria', 'Pneumonia', 
    'Diabetes', 'Hypertension'
]

# Disease Mapping for Medicine Recommendations
DISEASE_MAP = {
    'Fungal infection': 'Fungal infections',
    'Acne': 'Acne vulgaris',
    'GERD': 'Acidity, gastric issues',
    'Allergy': 'Allergy, redness',
    'Hypertension': 'High Blood Pressure',
    'Drug Reaction': 'Allergy, redness',
    'Peptic ulcer diseae': 'Stomach ulcers',
    'Diabetes': 'Diabetes management',
    'Gastroenteritis': 'Acidity, gastric issues',
    'Bronchial Asthma': 'Asthma, breathing issues',
    'Migraine': 'Headache, Migraine',
    'Jaundice': 'Liver issues',
    'Malaria': 'Infections (respiratory, skin)',
    'Typhoid': 'Bacterial infections',
    'Urinary tract infection': 'Bacterial infections',
    'Arthritis': 'Joint/muscle inflammation',
    'Osteoarthristis': 'Joint/muscle inflammation',
    'Common Cold': 'Cold, flu, fever, nasal congestion',
    'Pneumonia': 'Infections (respiratory, skin)',
    'Dimorphic hemmorhoids(piles)': 'Pain, inflammation',
}

# ==========================
# GLOBAL AI MODEL LOADING
# ==========================

ai_model = None
symptom_columns = []
desc_df = pd.DataFrame()
prec_df = pd.DataFrame()
formula_df = pd.DataFrame()
meds_df = pd.DataFrame()

def load_ai_assets():
    """Load AI model and datasets into global variables"""
    global ai_model, symptom_columns, desc_df, prec_df, formula_df, meds_df
    
    try:
        # Load model features
        if os.path.exists(FEATURES_PATH):
            with open(FEATURES_PATH, "rb") as f:
                symptom_columns = pickle.load(f)
            print(f"[OK] Loaded {len(symptom_columns)} model disease_model features")
        
        # Load ML model
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, "rb") as f:
                ai_model = pickle.load(f)
        
        # Load datasets
        if os.path.exists(SYMPTOM_DESCRIPTION_PATH):
            desc_df = pd.read_csv(SYMPTOM_DESCRIPTION_PATH)
        
        if os.path.exists(SYMPTOM_PRECAUTION_PATH):
            prec_df = pd.read_csv(SYMPTOM_PRECAUTION_PATH)
        
        if os.path.exists(FORMULA_PATH):
            formula_df = pd.read_csv(FORMULA_PATH)
        
        if os.path.exists(PAK_MEDICINES_PATH):
            meds_df = pd.read_csv(PAK_MEDICINES_PATH)
            
        print(f"[OK] AI assets loaded successfully. Model ready with {len(symptom_columns)} symptoms")
        
    except Exception as e:
        print(f"[ERROR] AI assets loading error: {e}")
        import traceback
        traceback.print_exc()

# Initialize AI assets on module load
load_ai_assets()

# ==========================
# HELPER FUNCTIONS
# ==========================

def _extract_json(text):
    """Pull a JSON object out of a Gemini response, tolerating ```json fences
    or stray text around it."""
    import re, json
    cleaned = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.MULTILINE).strip()
    match = re.search(r'\{.*\}', cleaned, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


def _trim(text, max_len=240):
    text = (text or "").strip()
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0] + "..."
    return text


def strict_gemini_response(symptoms, age=None, gender=None, is_search_mode=False):
    """
    STRICT Gemini function that NEVER mentions diseases or medicines.
    Returns a small structured dict (not one giant paragraph) so the UI can
    render short, scannable sections instead of a wall of text.
    """
    fallback = {
        "general_guidance": "Please consult a healthcare professional for accurate assessment.",
        "when_to_consult": "If symptoms persist or worsen, book an appointment with a doctor.",
        "emergency_signs": "Seek emergency care for severe pain, breathing difficulty, or loss of consciousness."
    }
    try:
        subject = symptoms if is_search_mode else ', '.join(symptoms)
        prompt = f"""
        USER INPUT: {subject}
        Age: {age}, Gender: {gender}

        STRICT SAFETY PROTOCOL:
        1. NEVER mention any specific disease name (e.g., Flu, Malaria, COVID).
        2. NEVER suggest any medications, drugs, or remedies.
        3. NEVER say "you have", "it sounds like", or provide a diagnosis.

        Respond with ONLY raw JSON (no markdown fences, no extra text) in exactly this shape:
        {{
          "general_guidance": "1-2 short sentences of general wellness guidance, max 220 characters",
          "when_to_consult": "1-2 short sentences on when to see a doctor, max 220 characters",
          "emergency_signs": "1-2 short sentences on red-flag symptoms needing emergency care, max 220 characters"
        }}
        Keep every field brief and scannable — no long paragraphs.
        """

        response = genai_client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt
        )
        data = _extract_json(response.text)
        if not data:
            return fallback

        return {
            "general_guidance": _trim(data.get("general_guidance") or fallback["general_guidance"]),
            "when_to_consult": _trim(data.get("when_to_consult") or fallback["when_to_consult"]),
            "emergency_signs": _trim(data.get("emergency_signs") or fallback["emergency_signs"]),
        }

    except Exception as e:
        error_str = str(e).lower()
        if '429' in error_str or 'quota' in error_str or 'exceeded' in error_str:
            print(f"Gemini Quota Exceeded: {e}")
            return {
                "general_guidance": "Our AI service is currently at capacity. Please try again later or consult a healthcare professional.",
                "when_to_consult": "If your symptoms are severe or worsening, seek medical attention promptly.",
                "emergency_signs": "Call emergency services for difficulty breathing, chest pain, severe bleeding, or loss of consciousness."
            }
        else:
            print(f"Strict Gemini Error: {e}")
            return fallback

def gemini_explain(disease, symptoms, age, gender):
    """Get a short, structured AI explanation for an ML-predicted disease.
    Returns a dict {meaning, precautions: [...], consult_doctor} instead of
    one long paragraph, so the UI can show it as compact bullet points."""
    fallback = {
        "meaning": "AI explanation currently unavailable.",
        "precautions": [],
        "consult_doctor": ""
    }
    try:
        prompt = f"""
        You are a health information assistant. This is NOT a medical diagnosis.

        Patient:
        Age: {age}
        Gender: {gender}
        Symptoms: {', '.join(symptoms)}

        ML predicted condition: {disease}

        Respond with ONLY raw JSON (no markdown fences, no extra text) in exactly this shape:
        {{
          "meaning": "1-2 short sentences explaining what this condition generally means, max 200 characters",
          "precautions": ["short precaution 1", "short precaution 2", "short precaution 3"],
          "consult_doctor": "1 short sentence on when to consult a doctor, max 150 characters"
        }}
        Do not suggest medicines. Keep everything brief and scannable, max 3 precautions.
        """
        response = genai_client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt
        )
        data = _extract_json(response.text)
        if not data:
            return fallback

        precautions = data.get("precautions") or []
        if isinstance(precautions, str):
            precautions = [precautions]
        precautions = [_trim(p, 120) for p in precautions[:3] if str(p).strip()]

        return {
            "meaning": _trim(data.get("meaning") or fallback["meaning"], 200),
            "precautions": precautions,
            "consult_doctor": _trim(data.get("consult_doctor") or "", 150),
        }
    except Exception as e:
        error_str = str(e).lower()
        if '429' in error_str or 'quota' in error_str or 'exceeded' in error_str:
            print(f"Gemini Quota Exceeded: {e}")
            return {
                "meaning": "AI service temporarily unavailable due to high demand. Please consult a healthcare professional.",
                "precautions": [],
                "consult_doctor": ""
            }
        else:
            print(f"Gemini explanation error: {e}")
            return fallback


def check_emergency_severity(symptoms):
    """Check if symptoms indicate emergency using Gemini"""
    try:
        prompt = f"Analyze these symptoms: {', '.join(symptoms)}. Is this a life-threatening emergency (like heart attack, stroke, severe trauma)? Respond with ONLY 'YES' or 'NO'."
        response = genai_client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt
        )
        return "YES" in response.text.upper().strip()
    except Exception as e:
        error_str = str(e).lower()
        if '429' in error_str or 'quota' in error_str or 'exceeded' in error_str:
            print(f"Gemini Quota Exceeded in severity check: {e}")
            return False  # Assume not emergency if can't check
        else:
            print(f"Severity Check Error: {e}")
            return False

def find_disease_row(df, disease_name, col='Disease', score_cutoff=85):
    """
    Look up a disease row by exact (case-insensitive) match first.
    If that fails (e.g. a typo/spelling mismatch between datasets, like
    'hemmorhoids' vs 'hemorrhoids'), fall back to fuzzy matching so a single
    inconsistent CSV entry doesn't silently produce 'Information pending review'.
    """
    if df is None or df.empty or col not in df.columns:
        return None

    exact = df[df[col].str.lower().str.strip() == disease_name.lower().strip()]
    if not exact.empty:
        return exact.iloc[0]

    # Fuzzy fallback
    choices = df[col].dropna().unique().tolist()
    if not choices:
        return None
    match = process.extractOne(disease_name, choices)
    if match and match[1] >= score_cutoff:
        best_row = df[df[col] == match[0]]
        if not best_row.empty:
            print(f"[FUZZY MATCH] '{disease_name}' -> '{match[0]}' (score {match[1]})")
            return best_row.iloc[0]

    return None


def get_medicine_recommendations(disease_name, generic_formula="", meds_df=None):
    """Return OTC, in-stock, non-prescription medicines for a given disease.

    - Uses the CSV (meds_df) to find candidates by Indication/Strength.
    - Then maps each candidate to the real Medicine table to ensure stock_quantity > 0.
    - CSV price is used as fallback only when the DB row is missing.
    """
    if meds_df is None or meds_df.empty:
        return []

    try:
        target_term = DISEASE_MAP.get(disease_name, disease_name)

        if 'Indication' not in meds_df.columns:
            return []

        matched_meds = meds_df[
            ((meds_df['Indication'].str.contains(target_term, case=False, na=False, regex=False)) |
             (meds_df['Strength'].str.contains(generic_formula, case=False, na=False, regex=False)))
            & (meds_df['Prescription Required'].astype(str).str.strip().str.lower() != 'yes')
        ]

        medicines = []
        for _, med_row in matched_meds.head(4).iterrows():
            drug_name = str(med_row.get('Drug Name', '')).strip()
            if not drug_name:
                continue

            raw_price = med_row.get('Price', 0)
            csv_price = float(raw_price) if pd.notna(raw_price) else None

            real_medicine = (
                Medicine.objects
                .filter(name__icontains=drug_name, stock_quantity__gt=0)
                .select_related('pharmacy')
                .first()
            )
            available = bool(real_medicine)

            medicines.append({
                "id": real_medicine.id if available else None,
                "available": available,
                "name": drug_name,
                "manufacturer": med_row.get('Manufacturer', 'N/A'),
                "price": float(real_medicine.price) if available and real_medicine else (csv_price if csv_price is not None else "TBD"),
                "pharmacy": real_medicine.pharmacy.name if (available and real_medicine and real_medicine.pharmacy) else None,
                "formula": generic_formula,
                "side_effects": med_row.get('Side Effects', 'N/A')
            })

        return medicines

    except Exception as e:
        print(f"Medicine Search Error: {e}")
        return []


# ==========================
# CUSTOMER DASHBOARD PAGES
# ==========================
@role_required('customer', 'admin', 'super_admin')
def customer_dashboard(request):
    """Default page when logging in"""
    context = _get_medicine_browse_context()
    context.update({
        'page_name': 'search',
        'base_template': get_base_template(request)
    })
    return render(request, 'customers_d/search_medicines.html', context)


def get_available_medicines():
    """Shared helper: returns active, in-stock medicines from approved pharmacies.
    Used by both customers_d and pages views for consistency."""
    return (
        Medicine.objects
        .select_related('pharmacy')
        .filter(
            is_banned=False,                    # Active medicines only
            stock_quantity__gt=0,               # Only in-stock medicines
            pharmacy__verification_status="approved"  # Only approved pharmacies
        )
        .order_by('name')
    )

def _get_medicine_browse_context():
    medicines = get_available_medicines()
    categories = Medicine.objects.values_list('category', flat=True).distinct()
    pharmacies = Pharmacy.objects.filter(is_verified=True).values_list('name', flat=True).distinct()
    return {
        'medicines': medicines,
        'categories': categories,
        'pharmacies': pharmacies,
    }

@role_required('customer', 'admin', 'super_admin')
def customer_medicine(request):
    # Your logic here (e.g., fetching products)
    return render(request, 'customers_d/medicine_list.html')

@role_required('customer', 'admin', 'super_admin')
def search_medicines(request):
    """Render search medicines page"""
    context = _get_medicine_browse_context()
    context.update({'page_name': 'search'})
    return render(request, 'customers_d/search_medicines.html', context)

@role_required('customer', 'admin', 'super_admin')
def symptom_checker(request):
    """Render symptom checker page with all available symptoms"""
    clean_symptoms = []
    
    if os.path.exists(TRAINING_DATA_PATH):
        df = pd.read_csv(TRAINING_DATA_PATH)
        target_cols = ['Disease', 'prognosis']
        clean_symptoms = sorted(
            [s.replace('_', ' ').title() for s in df.columns if s not in target_cols]
        )
    
    return render(request, 'customers_d/symptom_checker.html', {
        'page_name': 'symptom',
        'all_symptoms': clean_symptoms
    })

# customers_d/views.py
@login_required  # ✅ sirf login check — koi role restriction nahi
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    # Role ke hisaab se base template decide karo
    if request.user.role == 'pharmacy':
        base = 'dashboards/pharmacy_base.html'
    else:
        base = 'customers_d/customer_base.html'
    
    context = {
        'page_name': 'orders',
        'active_tab': 'orders',
        'orders': orders,
        'base_template': base,  # ✅ pharmacy ko pharmacy navbar mile
    }
    return render(request, 'customers_d/my_orders.html', context)

@role_required('customer', 'admin', 'super_admin')
def nearby_pharmacies(request):
    """Render nearby pharmacies page (DB-backed + template-driven geolocation sorting)."""
    from dashboards.models import Pharmacy

    pharmacies_qs = (
        Pharmacy.objects.filter(
            is_verified=True,
            latitude__isnull=False,
            longitude__isnull=False,
        )
        .select_related('user')
        .values(
            'id',
            'name',
            'latitude',
            'longitude',
            'address',
            'phone',
            'user__email',
        )
    )

    pharmacy_list = list(pharmacies_qs)

    # Fallback: agar koi location fields na hon to sab verified pharmacies
    if not pharmacy_list:
        pharmacy_list = list(
            Pharmacy.objects.filter(is_verified=True)
            .values('id', 'name', 'address', 'phone', 'user__email')
        )

    # Ensure JS can iterate safely (distance sorting will only apply where lat/lng exist)
    for ph in pharmacy_list:
        ph.setdefault('latitude', None)
        ph.setdefault('longitude', None)


    return render(
        request,
        'customers_d/nearby_pharmacies.html',
        {
            'page_name': 'pharmacies',
            'pharmacies_json': json.dumps(pharmacy_list),
            'pharmacies': Pharmacy.objects.filter(is_verified=True).select_related('user'),
        },
    )



@role_required('customer', 'admin', 'super_admin')
def upload_prescription(request):
    """Render upload prescription page"""
    return render(request, 'customers_d/upload_prescription.html', {'page_name': 'upload'})

@role_required('customer', 'admin', 'super_admin')
def customer_home(request):
    """Customer home page with cart count"""
    cart = Cart.objects.filter(user=request.user, is_active=True).first()
    cart_count = cart.items_count if cart else 0
    
    return render(request, "customers_d/customer_home.html", {
        "cart_count": cart_count,
        "base_template": get_base_template(request),
    })

# ==========================
# CART FUNCTIONALITY
# ==========================
@login_required
def add_to_cart(request):
    """Add product to cart - medicine_id aur product_id dono support karta hai"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request'})
    
    try:
        data = json.loads(request.body)
        # medicine_id aur product_id dono accept karo (compatibility ke liye)
        product_id = data.get('medicine_id') or data.get('product_id')
        quantity = int(data.get('quantity', 1))
        action = data.get('action')  # 'remove' action support

        product = get_object_or_404(Medicine, id=product_id)

        cart, created = Cart.objects.get_or_create(
            user=request.user,
            is_active=True
        )

        cart_item, item_created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )

        if action == 'remove' or quantity <= 0:
            cart_item.delete()
            current_qty = 0
            item_total = 0.0
        elif not item_created:
            cart_item.quantity = quantity
            cart_item.save()
            current_qty = cart_item.quantity
            item_total = float(cart_item.total_price)
        else:
            current_qty = cart_item.quantity
            item_total = float(cart_item.total_price)

        return JsonResponse({
            'success': True,
            'message': f'{product.name} has been added to the cart!" 🛒',
            'cart_count': cart.items.count(),
            'current_qty': current_qty,
            'item_total': item_total,
            'cart_total': float(cart.total_price),
            # Backward compatibility ke liye
            'item_name': product.name,
            'item_price': str(product.price),
            'item_quantity': current_qty,
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)

@login_required  # ✅ FIX: role_required hatao, sab logged-in users ke liye
def get_cart_count(request):
    """Get cart count for header"""
    try:
        cart = Cart.objects.filter(user=request.user, is_active=True).first()
        cart_count = cart.items_count if cart else 0
    except Exception:
        cart_count = 0
    
    return JsonResponse({'cart_count': cart_count})

@login_required  # ✅ pharmacy bhi cart dekh sake
def cart_view(request):
    """View cart page"""
    cart = Cart.objects.filter(user=request.user, is_active=True).first()
    
    if cart:
        # ✅ FIX 3: 'cart.cart_items' ki jagah 'cart.items' use kiya (correct related_name)
        cart_items = cart.items.select_related('product').all()
        total_price = cart.total_price
    else:
        cart_items = []
        total_price = 0
    
    context = {
        'cart_items': cart_items,
        'total_price': total_price,
        'cart_item_count': len(cart_items) if hasattr(cart_items, '__len__') else cart_items.count()
    }

    return render(request, 'orders/cart.html', context)

@role_required('customer', 'pharmacy', 'admin', 'super_admin')
def update_cart_item(request):
    """Update cart item quantity"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request'})
    
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        action = data.get('action')
        
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        
        if action == 'increase':
            cart_item.quantity += 1
            cart_item.save()
        elif action == 'decrease':
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()
            else:
                cart_item.delete()
        elif action == 'remove':
            cart_item.delete()
        
        cart = Cart.objects.get(user=request.user, is_active=True)
        
        return JsonResponse({
            'success': True,
            'quantity': cart_item.quantity if cart_item.quantity > 0 else 0,
            'item_total': str(cart_item.total_price) if cart_item.quantity > 0 else '0',
            'cart_total': str(cart.total_price),
            'cart_count': cart.items_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)

# ==========================
# AI SYMPTOM CHECKER - UPDATED STRICT VERSION
# ==========================

@role_required('customer', 'admin', 'super_admin')
@require_POST
def predict_symptom(request):
    """Predict disease based on symptoms using AI model - STRICT VERSION"""
    
    try:
        # Parse request data
        data = json.loads(request.body)
        
        mode = data.get("mode", "ml")
        user_selected = data.get("symptoms", [])
        user_age = int(data.get("age", 25))
        user_gender = data.get("gender", "Male")
        search_term = data.get("search_term", "").strip()
        
        disclaimer = "This AI-based symptom checker is for informational purposes only and does not replace professional medical advice."
        
        print(f"📋 Mode: {mode}, Symptoms: {user_selected}, Search: '{search_term}'")
        
        # ============================================
        # DECISION TREE - STRICT VERSION
        # ============================================
        
        # 1. SEARCH MODE OR SEARCH TERM (Strict Gemini tabhi jab card selected na hon)
        if (mode == "search" or search_term) and not user_selected:
            print("🔍 FREE TEXT SEARCH → Strict Gemini Only")
            gemini_text = strict_gemini_response(
                search_term if search_term else ', '.join(user_selected),
                user_age, 
                user_gender,
                is_search_mode=True
            )
            return JsonResponse({
                "status": "success",
                "source": "gemini_strict",
                "fallback_explanation": gemini_text,
                "disclaimer": disclaimer,
                "mode_used": "search"
            })
        
        # 2. NO SYMPTOMS SELECTED → STRICT GEMINI
        if not user_selected:
            print("⚠️ No symptoms selected → Strict Gemini")
            gemini_text = strict_gemini_response(
                "No specific symptoms provided",
                user_age,
                user_gender,
                is_search_mode=True
            )
            return JsonResponse({
                "status": "success",
                "source": "gemini_strict",
                "fallback_explanation": gemini_text,
                "disclaimer": disclaimer
            })
        
        # 3. MODEL AVAILABILITY CHECK
        if ai_model is None:
            return JsonResponse({
                "status": "error", 
                "message": "AI Model not loaded"
            })
        
        # ============================================
        # SYMPTOM MATCHING (ONLY FOR CHECKBOX SELECTIONS)
        # ============================================
        
        # IMPORTANT: We ONLY process user_selected (checkboxes), NEVER search terms
        input_vector = [0] * len(symptom_columns)
        matched_symptoms = []
        
        for user_symptom in user_selected:
            cleaned = str(user_symptom).lower().strip().replace(" ", "_")
            
            # Direct mapping to 132 features
            found = False
            for idx, col in enumerate(symptom_columns):
                col_clean = col.lower().strip().replace(" ", "_")
                if cleaned == col_clean:
                    input_vector[idx] = 1
                    matched_symptoms.append(col)
                    found = True
                    print(f"✅ Exact match: {user_symptom} -> {col}")
                    break
            
            # NO FUZZY MATCHING - If not in 132 features, reject
            if not found:
                print(f"❌ {user_symptom} not in 132 features → Will trigger Gemini")
        
        print(f"📊 Matched {len(matched_symptoms)}/{len(user_selected)} symptoms to 132 features")
        
        # ============================================
        # NOT ALL SYMPTOMS MATCHED → STRICT GEMINI
        # ============================================
        
        if len(matched_symptoms) == 0:
            print("⚠️ No symptoms matched 132 features → Strict Gemini")
            gemini_text = strict_gemini_response(
                user_selected,
                user_age,
                user_gender,
                is_search_mode=False
            )
            return JsonResponse({
                "status": "success",
                "source": "gemini_strict",
                "fallback_explanation": gemini_text,
                "disclaimer": disclaimer,
                "matched_count": len(matched_symptoms),
                "total_symptoms": len(user_selected)
            })
        
        # ============================================
        # ALL SYMPTOMS MATCHED → ML MODEL PATH
        # ============================================
        
        # Only reach here if ALL user symptoms are in the 132 features
        
        # Prepare Input
        input_df = pd.DataFrame([input_vector], columns=symptom_columns)
        print(f"📈 ML Model Input: {input_df.shape}")
        
        # Get Predictions
        probs = ai_model.predict_proba(input_df)[0]
        diseases = ai_model.classes_
        top_3_idx = probs.argsort()[-3:][::-1]
        top_confidence = max(probs) * 100
        
        print(f"🎯 Top confidence: {top_confidence:.2f}%")
        
        # Low Confidence → Strict Gemini
        if top_confidence < 25:
            print("📉 Low confidence (<25%) → Strict Gemini")
            gemini_text = strict_gemini_response(
                user_selected,
                user_age,
                user_gender,
                is_search_mode=False
            )
            return JsonResponse({
                "status": "success",
                "source": "gemini_strict",
                "fallback_explanation": gemini_text,
                "disclaimer": disclaimer,
                "ml_confidence": top_confidence
            })
        
        # ============================================
        # HIGH CONFIDENCE ML RESULTS
        # ============================================
        
        results = []
        otc_age_allowed = 12 <= user_age <= 60
        
        for idx in top_3_idx:
            disease_name = str(diseases[idx]).strip()
            confidence = round(probs[idx] * 100, 2)
            
            # Get Generic Formula
            generic_formula = "Consult Specialist"
            f_row = find_disease_row(formula_df, disease_name)
            if f_row is not None:
                generic_formula = f_row['Generic_Formula']
            
            # Get Description
            description = "Information pending review."
            d_row = find_disease_row(desc_df, disease_name)
            if d_row is not None:
                description = d_row['Description']
            
            # Get Precautions
            precautions = []
            p_row = find_disease_row(prec_df, disease_name)
            if p_row is not None:
                for i in range(1, 5):
                    val = p_row.get(f'Precaution_{i}')
                    if pd.notna(val) and str(val).strip():
                        precautions.append(str(val).strip())
            
            # Safety Checks
            is_dangerous = disease_name.lower() in [d.lower() for d in DANGEROUS_DISEASES]
            otc_allowed = (not is_dangerous) and otc_age_allowed
            
            # Get Medicines — centralized function use kar rahe hain
            medicines = []
            if otc_allowed:
                medicines = get_medicine_recommendations(
                    disease_name,
                    generic_formula=generic_formula,
                    meds_df=meds_df
                )

            # AI Explanation (Top result only)
            ai_explanation = None
            emergency_flag = False
            if idx == top_3_idx[0]:
                ai_explanation = gemini_explain(disease_name, user_selected, user_age, user_gender)
                # FIX: emergency check ab sirf dangerous-list diseases ke liye chalta hai.
                # Pehle har top-1 result (chahe GERD jaisi mild condition ho) pe Gemini se
                # "is this life-threatening?" poocha ja raha tha, jiska jawab inconsistent
                # aa sakta hai — isi wajah se safe conditions pe bhi kabhi kabhi
                # "Emergency Alert" ban jata tha. Ab sirf genuinely dangerous diseases
                # (DANGEROUS_DISEASES list) ke liye hi ye check chalega.
                if is_dangerous:
                    emergency_flag = check_emergency_severity(user_selected)

            # Compile Result
            results.append({
                "disease": disease_name,
                "emergency": emergency_flag,

                "confidence": confidence,
                "risk": "High" if is_dangerous or confidence > 75 else "Medium",
                "description": description,
                "precautions": precautions,
                "generic_formula": generic_formula,
                "otc_allowed": otc_allowed,
                "medicines": medicines,
                "ai_explanation": ai_explanation
            })
        
        # ============================================
        # FINAL ML RESPONSE
        # ============================================
        
        return JsonResponse({
            "status": "success",
            "source": "ml",
            "predictions": results,
            "disclaimer": disclaimer,
            "matched_symptoms": matched_symptoms
        })
        
    except Exception as e:
        print(f"❌ Prediction error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Always fallback to Strict Gemini
        try:
            gemini_text = strict_gemini_response(
                user_selected if 'user_selected' in locals() else ["Error occurred"],
                user_age if 'user_age' in locals() else 25,
                user_gender if 'user_gender' in locals() else "Male",
                is_search_mode=False
            )
            return JsonResponse({
                "status": "success",
                "source": "gemini_strict",
                "fallback_explanation": gemini_text,
                "disclaimer": disclaimer,
                "error": str(e)[:100]
            })
        except:
            return JsonResponse({
                "status": "error", 
                "message": "System error. Please try again or consult a doctor."
            })

# ==========================
# REPORT DOWNLOAD
# ==========================

@role_required('customer', 'admin', 'super_admin')
def download_report(request, disease_name): 
    """Generate and download PDF report - SECURE VERSION"""
    # Decode URL parameters
    disease_name = urllib.parse.unquote(disease_name)
    
    description = "No description available."
    d_row = find_disease_row(desc_df, disease_name)
    if d_row is not None and 'Description' in d_row.index:
        description = d_row['Description']

    precautions_list = []
    p_row = find_disease_row(prec_df, disease_name)
    if p_row is not None:
        for i in range(1, 5):
            col_name = f'Precaution_{i}'
            if col_name in p_row.index:
                val = p_row.get(col_name)
                if pd.notna(val) and str(val).strip():
                    precautions_list.append(str(val).strip())
    
    age = request.GET.get('age', 'N/A')
    gender = request.GET.get('gender', 'N/A')
    customer_name = request.user.get_full_name() or request.user.username
    disease = disease_name.title()
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="PharmaHub_{disease}_Report.pdf"'
    
    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    
    # Header
    p.setFont("Helvetica-Bold", 28)
    p.setFillColorRGB(0, 0.5, 0.4)
    p.drawCentredString(width/2, height - 50, "PHARMAHUB")
    
    p.setFont("Helvetica", 10)
    p.setFillColor(colors.grey)
    p.drawCentredString(width/2, height - 65, "Your Trusted AI-Powered Health Assistant")
    
    p.setStrokeColor(colors.lightgrey)
    p.line(50, height - 75, width - 50, height - 75)
    
    # Patient Info
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, height - 100, "PATIENT INFORMATION")
    p.setFont("Helvetica", 10)
    p.drawString(50, height - 120, f"Name: {customer_name}")
    p.drawString(250, height - 120, f"Age: {age}")
    p.drawString(400, height - 120, f"Gender: {gender}")
    p.drawString(50, height - 135, f"Date: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    
    p.line(50, height - 145, width - 50, height - 145)
    
    # Diagnosis
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, height - 170, f"DIAGNOSIS: {disease.upper()}")
    p.setFont("Helvetica-Bold", 11)
    p.drawString(50, height - 190, "Condition Overview:")
    p.setFont("Helvetica", 10)
    
    # Description
    text_obj = p.beginText(50, height - 205)
    text_obj.setLeading(14)
    desc_lines = [description[i:i+95] for i in range(0, len(description), 95)]
    for line in desc_lines:
        text_obj.textLine(line)
    p.drawText(text_obj)
    
    # Precautions
    current_y = height - 320
    p.setFont("Helvetica-Bold", 11)
    p.drawString(50, current_y, "RECOMMENDED PRECAUTIONS:")
    p.setFont("Helvetica", 10)
    
    if precautions_list:
        for i, prec in enumerate(precautions_list):
            p.drawString(70, current_y - 20 - (i*15), f"• {prec}")
    else:
        p.drawString(70, current_y - 20, "No specific precautions found.")
    
    # Footer
    p.setFont("Helvetica-Oblique", 8)
    p.drawCentredString(width/2, 30, "This is an AI generated report. Please consult a doctor for formal diagnosis.")
    
    p.showPage()
    p.save()
    return response


# =====================================================
# CHECKOUT & ORDER VIEWS
# =====================================================

DELIVERY_FEE = 40  # PKR

# =============================================
# Order Detail View - customers_d app
# =============================================
@login_required
def order_detail(request, order_id):
    try:
        # Variable ka naam 'order' rakha hai
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect('customers_d:my_orders')

    # Role ke hisaab se base_template
    if request.user.role == 'pharmacy':
        base = 'dashboards/pharmacy_base.html'
    else:
        base = 'customers_d/customer_base.html'

    return render(request, 'customers_d/order_detail.html', {
        'order': order,
        'base_template': base,
    })
    
# customers_d/views.py (File ke aakhir mein replace karein)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Prescription, CustomerNotification
from dashboards.models import Pharmacy
from django.contrib.auth.models import User
from authentication.decorators import role_required

# Centralized Notification Model from admin_panel
from admin_panel.models import Notification 

@role_required('customer', 'admin', 'super_admin')
def upload_prescription(request):
    
    # 1. POST Logic: Prescription upload karne ke liye
    if request.method == 'POST':
        pharmacy_id = request.POST.get('pharmacy')
        image = request.FILES.get('prescription_image')
        
        if pharmacy_id and image:
            # Pharmacy object fetch karna taake location/user mil sakay
            pharmacy_obj = get_object_or_404(Pharmacy, id=pharmacy_id)
            
            # Prescription record create karna
            new_prx = Prescription.objects.create(
                customer=request.user,
                pharmacy=pharmacy_obj.user, 
                prescription_image=image,
                status='pending'
            )
            
            # --- NOTIFICATION LOGIC (Fixed for real-time count & badge) ---
            msg_content = f"You have received a new prescription (ID: PRX-{new_prx.id}) from customer '{request.user.username}' for verification."
            
            # Purana helper call
            send_pharmacy_notification(
                pharmacy_user=pharmacy_obj.user,
                message=msg_content,
                prescription=new_prx
            )
            
            # 🌟 NEW FIX: Dashboards model dynamic update for real-time unread badge count
            try:
                from dashboards.models import PharmacyNotification
                PharmacyNotification.objects.create(
                    user=pharmacy_obj.user,
                    message=msg_content,
                    prescription=new_prx,
                    is_read=False
                )
                print(f"--> [SUCCESS] Pharmacy Notification badge row inserted for {pharmacy_obj.user.username}")
            except Exception as badge_err:
                print(f"--> [BADGE ERROR BYPASSED]: {badge_err}")
            # --------------------------------------------------------

            # 🌟 NEW FIX: EMAIL TO PHARMACY USER
            try:
                # Agar pharmacy user ki koi email feed registered hai
                pharmacy_email = pharmacy_obj.user.email
                if pharmacy_email:
                    subject = f"🚨 New Prescription Uploaded - PRX-{new_prx.id}"
                    email_body = (
                        f"Hello {pharmacy_obj.user.username},\n\n"
                        f"A patient ({request.user.username}) has uploaded a new prescription for your review.\n\n"
                        f"Prescription ID: PRX-{new_prx.id}\n"
                        f"Status: Pending Review\n\n"
                        f"Please log in to your PharmaHub Dashboard to review the image and send a price quote.\n\n"
                        f"Regards,\nPharmaHub Team."
                    )
                    
                    send_mail(
                        subject=subject,
                        message=email_body,
                        from_email=settings.EMAIL_HOST_USER,
                        recipient_list=[pharmacy_email],
                        fail_silently=False # Terminal par errors show karega agar fail hua toh
                    )
                    print(f"--> [SUCCESS EMAIL] Notification email sent to pharmacy: {pharmacy_email}")
                else:
                    print("--> [EMAIL WARNING] Pharmacy user has no email defined in their account.")
            except Exception as mail_err:
                print(f"--> [EMAIL SENDING FAILED]: {mail_err}")
            # --------------------------------------------------------

            messages.success(request, "Prescription sent successfully!")
            return redirect('customers_d:upload_prescription')

    # 2. GET Logic: Notifications aur Verified Pharmacies fetch karne ke liye
    notifications = CustomerNotification.objects.filter(
        user=request.user, 
        is_read=False
    ).order_by('-created_at')
    
    # Verified pharmacies dropdown ke liye
    pharmacies_list = Pharmacy.objects.filter(is_verified=True)
    
    context = {
        'notifications': notifications,
        'pharmacies': pharmacies_list,
        'page_name': 'upload'
    }
    return render(request, 'customers_d/upload_prescription.html', context)
# customers_d/views.py

def get_quote_details(request, prx_id):
    prescription = get_object_or_404(Prescription, id=prx_id, customer=request.user)
    quote_items = prescription.quote_items.all()
    
    # JSON format mein data bhejna
    items_data = []
    for item in quote_items:
        items_data.append({
            'id': item.medicine.id,
            'name': item.medicine.name,
            'price': str(item.price_at_quote),
        })
        
    return JsonResponse({'items': items_data})

# customers_d/views.py mein ye function add karein:
@role_required('customer', 'admin', 'super_admin')
def notification_c_view(request):
    """Customer ki sari notifications fetch karne ke liye"""
    notifications = CustomerNotification.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    # Optional: Jab user is page par aaye toh notifications ko 'read' mark kar dein
    # notifications.update(is_read=True)

    return render(request, 'customers_d/notification_c.html', {
        'notifications': notifications,
        'page_name': 'notifications'
    })
    
from django.shortcuts import render, get_object_or_404
from .models import Prescription, QuoteItem  # Apne models ke name check kr lein

def prescription_details_view(request, prx_id):
    # Prescription fetch karein ya 404 error dein agar na milay
    prescription = get_object_or_404(Prescription, id=prx_id)
    
    # Woh items fetch karein jo pharmacy ne is prescription ke against add kiye hain
    quote_items = QuoteItem.objects.filter(prescription=prescription)
    
    context = {
        'p': prescription,
        'quote_items': quote_items,
    }
    return render(request, 'customers_d/prescription_details.html', context)

@login_required
@role_required('customer', 'pharmacy', 'admin', 'super_admin')
def reorder(request, order_id):
    """Previous order ki saari items naye cart mein daal do — stock check ke saath"""
    original_order = get_object_or_404(Order, id=order_id, user=request.user)

    # Purana active cart deactivate karo
    Cart.objects.filter(user=request.user, is_active=True).update(is_active=False)

    # Naya cart banao
    new_cart = Cart.objects.create(user=request.user, is_active=True)

    items_added  = 0
    out_of_stock = []
    partial_stock = []

    for item in original_order.items.all():
        medicine      = item.product
        requested_qty = item.quantity
        available_qty = medicine.stock_quantity

        if available_qty <= 0:
            out_of_stock.append(medicine.name)
            continue

        if available_qty < requested_qty:
            actual_qty = available_qty
            partial_stock.append(
                f"{medicine.name} ({requested_qty} maanga, {actual_qty} available)"
            )
        else:
            actual_qty = requested_qty

        CartItem.objects.create(
            cart=new_cart,
            product=medicine,
            quantity=actual_qty
        )
        items_added += 1

    # Messages
    if items_added > 0:
        messages.success(request, f"✅ {items_added} item(s) cart mein add ho gaye!")
    for msg in partial_stock:
        messages.warning(request, f"⚠️ Limited stock: {msg}")
    for name in out_of_stock:
        messages.error(request, f"❌ Out of stock: {name}")

    if items_added == 0:
        messages.error(request, "Is order ki saari medicines out of stock hain.")
        return redirect('customers_d:my_orders')

    return redirect('customers_d:cart_view')



# def reorder_action(request, order_id):
#     (deleted as per Flow 6 requirement)


from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import CustomerNotification  # <--- Asli target dushman!


@login_required
@require_POST
def cancel_order(request, order_id):
    """Cancel a pending order and restore stock."""
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.status != 'Pending':
        messages.error(request, 'Only pending orders can be cancelled.')
        return redirect('customers_d:my_orders')

    # Restore stock quantities
    for item in order.items.all():
        med = item.product
        med.stock_quantity += item.quantity
        med.save()

    order.status = 'Cancelled'
    order.save()

    # Mark payment failed if payment exists
    try:
        if hasattr(order, 'payment') and order.payment:
            order.payment.status = 'failed'
            order.payment.save()
    except Exception:
        pass

    messages.success(request, 'Order cancelled successfully. Stock restored.')
    return redirect('customers_d:my_orders')


@login_required
@require_POST
def clear_customer_notifications_api(request):
    try:
        # Request karne wale user ke saare customer notifications delete kar do
        deleted_count, _ = CustomerNotification.objects.filter(user=request.user).delete()
        
        print(f"--> [SUCCESS] Deleted {deleted_count} customer notifications.")
        
        return JsonResponse({
            'success': True, 
            'message': 'All customer notifications cleared successfully!'
        })
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': str(e)
        }, status=500)