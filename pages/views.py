import json
import os
import re
from typing import List, Dict, Optional, Tuple, Any

import requests
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

from dashboards.models import Medicine, Pharmacy

# ==================== LANGUAGE DETECTION UTILITY ====================

def detect_language(text: str) -> str:
    """
    Detect the language of user input.
    
    Returns:
        str: 'ur' for Urdu/Roman Urdu, 'en' for English, 'unknown' if can't detect
    """
    if not text or len(text.strip()) < 2:
        return 'unknown'
    
    text_lower = text.lower()
    
    # Roman Urdu indicators (common words)
    roman_urdu_words = [
        'hai', 'hain', 'kya', 'ka', 'ki', 'ke', 'se', 'ko', 'ne', 'bhi',
        'tha', 'the', 'thi', 'thin', 'ho', 'hoga', 'hogi', 'honge',
        'mera', 'meri', 'mere', 'tera', 'teri', 'tere', 'apna', 'apni',
        'yeh', 'wo', 'jo', 'so', 'ab', 'tab', 'kab', 'kahan', 'kyun',
        'acha', 'theek', 'sahi', 'galat', 'nai', 'nahi', 'haan', 'ji',
        'dawai', 'dawa', 'dard', 'bukhar', 'khansi', 'zukam', 'sehat',
        'hakeem', 'mareez', 'bimar', 'ilaj'
    ]
    
    # Count Roman Urdu words
    words = text_lower.split()
    roman_urdu_count = sum(1 for word in words if word in roman_urdu_words)
    
    # Urdu script detection (Unicode range for Urdu/Arabic)
    urdu_script_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
    urdu_chars = urdu_script_pattern.findall(text)
    
    # If contains Urdu script
    if len(urdu_chars) > 0:
        return 'ur'
    
    # If significant Roman Urdu words (30% or more)
    if words and (roman_urdu_count / len(words)) >= 0.3:
        return 'ur'  # Treat as Urdu/Roman Urdu
    
    # Default to English for simplicity (avoid langdetect dependency)
    return 'en'


def get_response_language(user_lang: str) -> str:
    """
    Determine response language based on user language.
    
    Args:
        user_lang (str): Detected user language
    
    Returns:
        str: Language code for response
    """
    if user_lang == 'ur':
        return 'ur'  # Respond in Urdu/Roman Urdu
    return 'en'  # Default to English


# ==================== TEMPLATE HELPER FUNCTIONS ====================

def get_base_template(request):
    """Determine base template based on user role and request path"""
    if not request.user.is_authenticated:
        return "pharmacy/base.html"

    if "customer_dashboard" in request.path or "customers_d" in request.path:
        return "customers_d/customer_base.html"
    if "pharmacy_dashboard" in request.path or "dashboards" in request.path:
        return "dashboards/pharmacy_base.html"

    user_role = getattr(request.user, "role", "").lower()
    if user_role == "customer":
        return "customers_d/customer_base.html"
    if user_role in ("pharmacy", "pharmacist"):
        return "dashboards/pharmacy_base.html"

    return "customers_d/customer_base.html"


# ==================== PAGE VIEWS ====================

def pharmacies(request):
    """Display all verified pharmacies"""
    all_pharmacies = Pharmacy.objects.filter(is_verified=True)
    
    return render(request, "pages/pharmacies.html", {
        "base_template": get_base_template(request),
        "pharmacies": all_pharmacies
    })
  
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from dashboards.models import Pharmacy, Medicine

def view_shop(request, pharmacy_id):
    """Particular pharmacy ki details aur uski specific inventory show krwana"""
    
    # 🛑 FIX: Agar data verification status 'approved' nahi h testing me, to sirf id se check krein
    # Taki status pending hone par b page 404 error na de test krte huwe.
    pharmacy = get_object_or_404(Pharmacy, id=pharmacy_id)
    
    # Sirf is pharmacy ke user account ki medicines nikalain
    medicines = Medicine.objects.filter(user=pharmacy.user)
    
    # Shop ke andar medicine search filter logic
    search_query = request.GET.get('search_medicine', '').strip()
    if search_query:
        medicines = medicines.filter(name__icontains=search_query) | medicines.filter(brand__icontains=search_query)

    context = {
        'pharmacy': pharmacy,
        'medicines': medicines,
        'search_query': search_query,
        'base_template': get_base_template(request), 
    }
    return render(request, 'pages/view_shop.html', context)    




# views.py mein medicine view ko update karein
from customers_d.views import get_available_medicines

def medicine(request):
    medicines_list = get_available_medicines()
    # NOTE: medicines_list is ordered by 'name' (see get_available_medicines).
    # DISTINCT on a queryset that carries an ORDER BY on a different field
    # makes each row unique per (category, name) pair instead of per
    # category alone, producing duplicate category values. Reset ordering
    # to the field we're actually deduping on before calling .distinct().
    categories = (
        medicines_list.order_by('category')
        .values_list('category', flat=True)
        .distinct()
    )
    
    return render(request, "pages/medicine.html", {
        "base_template": get_base_template(request),
        "medicines": medicines_list,  # Seedha queryset
        "categories": categories
    
    })


def about(request):
    """About page view"""
    return render(request, "pages/about.html", {
        "base_template": get_base_template(request)
    })


def contact(request):
    """Contact page view"""
    return render(request, "pages/contact.html", {
        "base_template": get_base_template(request)
    })


def help(request):
    """Help page view"""
    return render(request, "pages/help.html", {
        "base_template": get_base_template(request)
    })




def is_pharmahub_related(text: str) -> tuple:
    """Check if message is related to PharmaHub medicines and services"""
    text_lower = text.lower()
    
    # Allowed keywords
    allowed_keywords = [
        # English
        'medicine', 'med', 'tablet', 'capsule', 'syrup', 'injection', 'dose', 'pill',
        'paracetamol', 'panadol', 'brufen', 'disprin', 'antibiotic',
        'pain', 'fever', 'cough', 'flu', 'cold', 'headache', 'stomach',
        'pharmacy', 'drug', 'prescription', 'doctor',
        'order', 'delivery', 'shipping', 'track', 'payment', 'price',
        
        # Roman Urdu
        'dawai', 'dawa', 'dard', 'bukhar', 'khansi', 'zukam', 'sehat',
        'hakeem', 'mareez', 'bimar', 'ilaj',
        
        # Platform related
        'pharmahub', 'hub', 'order', 'track',
    ]
    
    # Blocked topics
    blocked_keywords = [
        'cricket', 'football', 'sports', 'match', 'movie', 'film',
        'politics', 'election', 'party', 'love', 'relationship',
        'job', 'interview', 'career', 'crypto', 'bitcoin',
    ]
    
    # Check blocked topics first
    for keyword in blocked_keywords:
        if keyword in text_lower:
            return False, "topic_blocked"
    
    # Check allowed topics
    for keyword in allowed_keywords:
        if keyword in text_lower:
            return True, "allowed"
    
    # Short messages (greetings)
    if len(text_lower.split()) <= 3:
        greetings = ['hi', 'hello', 'hey', 'salam', 'assalam']
        if any(word in text_lower for word in greetings):
            return True, "greeting"
    
    return False, "not_related"


# ==================== GROQ API FUNCTIONS ====================

def get_groq_response(
    system_prompt: str, 
    user_message: str, 
    api_key: str, 
    model_name: str,
    history: Optional[List[Dict[str, str]]] = None,
    max_tokens: int = 300,
    temperature: float = 0.7
) -> Tuple[Optional[str], Optional[str]]:
    """Get response from Groq API with conversation history"""
    
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    
    GROQ_MODELS = {
        "llama-3.3-70b-versatile": "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant": "llama-3.1-8b-instant",
        "mixtral-8x7b-32768": "mixtral-8x7b-32768",
        "gemma2-9b-it": "gemma2-9b-it",
    }
    
    if model_name not in GROQ_MODELS:
        return None, f"Invalid model name"
    
    # Build messages
    messages = [{"role": "system", "content": system_prompt}]
    
    if history and isinstance(history, list):
        for item in history[-6:]:
            if (isinstance(item, dict) and 
                item.get("role") in ("user", "assistant") and 
                item.get("content")):
                messages.append({"role": item["role"], "content": item["content"]})
    
    messages.append({"role": "user", "content": user_message})
    
    request_body = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    
    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json=request_body,
            timeout=30
        )
        
        result = response.json()
        
        if response.status_code >= 400:
            error_msg = result.get("error", {}).get("message", "Groq service error")
            return None, f"Error {response.status_code}: {error_msg}"
        
        reply = (result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip())
        
        return reply, None
        
    except Exception as e:
        return None, str(e)


def get_groq_response_with_history(
    system_prompt: str, 
    user_message: str, 
    history: List[Dict[str, str]], 
    api_key: str, 
    model_name: str,
    max_tokens: int = 300,
    temperature: float = 0.7
) -> Tuple[Optional[str], Optional[str]]:
    """Wrapper with history"""
    return get_groq_response(
        system_prompt=system_prompt,
        user_message=user_message,
        api_key=api_key,
        model_name=model_name,
        history=history,
        max_tokens=max_tokens,
        temperature=temperature
    )


# ==================== MULTILINGUAL SYSTEM PROMPTS ====================

def get_system_prompt(language: str = 'en') -> str:
    """
    Get system prompt in appropriate language.
    
    Args:
        language (str): 'en' for English, 'ur' for Urdu/Roman Urdu
    
    Returns:
        str: System prompt in requested language
    """
    
    if language == 'ur':
        return """آپ PharmaHub Assistant ہیں، پاکستان میں PharmaHub فارمیسی پلیٹ فارم کے لیے AI مددگار۔

اہم قوانین:
1. صرف ادویات، فارمیسی سروسز، آرڈرز اور صحت کی مصنوعات کے بارے میں سوالات کے جواب دیں۔
2. کبھی بھی ذاتی معلومات نہ مانگیں (CNIC، فون، ای میل، پتہ)۔
3. ہمیشہ طبی مشورے کے لیے ڈاکٹر سے رجوع کرنے کا مشورہ دیں۔
4. جواب 150 الفاظ سے کم رکھیں۔
5. صارف اردو یا رومن اردو میں بات کر رہا ہے - اردو/رومن اردو میں جواب دیں۔

اجازت شدہ موضوعات:
- ادویات کی قیمتیں، دستیابی، استعمال، مضر اثرات
- آرڈر ٹریکنگ، ڈلیوری، ادائیگی
- فارمیسی کے مقامات، اوقات
- عام صحت کی علامات (بخار، درد، کھانسی)
- PharmaHub پلیٹ فارم کا استعمال

مثال:
صارف: "paracetamol ki price kya hai?"
Assistant: "Paracetamol 500mg کی 10 tablets کی قیمت Rs. 30 ہے۔ یہ درد اور بخار میں استعمال ہوتی ہے۔ کیا آپ کو کسی specific brand کی ضرورت ہے؟"
"""
    else:
        return """You are PharmaHub Assistant, an AI helper for PharmaHub pharmacy platform in Pakistan.

IMPORTANT RULES:
1. ONLY answer questions about medicines, pharmacy services, orders, and health products.
2. NEVER ask for personal information (CNIC, phone, email, address).
3. ALWAYS recommend consulting a doctor for medical advice.
4. Keep responses under 150 words.
5. The user is speaking in English - respond in English only.

ALLOWED TOPICS:
- Medicine prices, availability, uses, side effects
- Order tracking, delivery, payment
- Pharmacy locations, timings
- Common health symptoms (fever, pain, cough)
- How to use PharmaHub platform

EXAMPLE:
User: "How can I track my order?"
Assistant: "You can track your order by logging into your account and visiting 'My Orders' section. Would you like me to help you with the order number?"
"""






def privacy_policy(request):
    return render(request, 'pages/privacy.html')


def terms(request):
    return render(request, 'pages/terms.html')

def terms_of_service(request):
    return render(request, 'pages/terms.html')