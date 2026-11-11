import json
import uuid
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction

# 1. Models from OTHER apps (Absolute imports)
from dashboards.models import Medicine
from customers_d.models import Cart, CartItem

# 2. Models from THIS app (Relative import)
from .models import Order, OrderItem

# =============================================
# Medicine List Page
# =============================================
def medicine(request):
    medicines_list = Medicine.objects.all()
    # Distinct categories nikalne ke liye
    categories = Medicine.objects.values_list('category', flat=True).distinct()
    
    # Role ke hisaab se base template
    if not request.user.is_authenticated:
        base = 'pharmacy/base.html'  # Guest user: full public navbar
    elif hasattr(request.user, 'role') and request.user.role == 'pharmacy':
        base = 'dashboards/pharmacy_base.html'
    else:
        base = 'customers_d/customer_base.html'
    
    return render(request, "orders/medicine.html", { 
        'medicines_list': medicines_list,
        'categories': categories,
        'base_template': base,
    })

# =============================================
# ADD TO CART API (With Multi-Vendor Logic)
# =============================================
@require_POST
@login_required  # ✅ proper decorator
def add_to_cart_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Pehly login karein!'}, status=401)
    
    try:
        data = json.loads(request.body)
        m_id = data.get('medicine_id') 
        qty = int(data.get('quantity', 1))
        action = data.get('action') # New field

        product = Medicine.objects.get(id=m_id)
        cart = Cart.objects.filter(user=request.user, is_active=True).first()

        if not cart:
            cart = Cart.objects.create(user=request.user, is_active=True)
        
        # 🎯 ====================================================
        # 🌟 MULTI-VENDOR PHARMACY CONFLICT CHECK
        # ====================================================
        existing_items = cart.items.all()
        
        # Agar cart khali nahi hai aur user naya item add karne ki koshish kar raha hai
        if existing_items.exists() and action != 'remove' and qty > 0:
            # Cart ke pehle item ka user (pharmacy owner) nikalen
            first_item_owner = existing_items.first().product.user
            
            # Agar naye product ka user (pharmacy) aur cart ke purane items ka user alag hain
            if first_item_owner != product.user:
                # Dono pharmacies ke names dynamic nikalen agar profiles bani hui hain
                existing_name = "the previous pharmacy"
                if hasattr(first_item_owner, 'pharmacy'):
                    existing_name = first_item_owner.pharmacy.name
                    
                new_name = "this pharmacy"
                if hasattr(product.user, 'pharmacy'):
                    new_name = product.user.pharmacy.name

                # Frontend ko signal bhejen taake alert box readable message dikhaye aur confirm box chalaye
                return JsonResponse({
                    "success": False,
                    "conflict": True,
                    "message": f"Your cart already contains items from '{existing_name}'. To maintain coordinated shipping, you can only order from one pharmacy at a time. Would you like to clear your current cart and start shopping from '{new_name}'?"
                })
        # ====================================================

        cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        
        # Agar action remove hai ya quantity 0 hai to delete kar do
        if action == 'remove' or qty <= 0:
            cart_item.delete()
            current_qty = 0
            item_total = 0
        else:
            cart_item.quantity = qty
            cart_item.save()
            current_qty = cart_item.quantity
            item_total = float(cart_item.total_price)

        return JsonResponse({
            'success': True, 
            'cart_count': cart.items.count(),
            'current_qty': current_qty,
            'item_total': item_total,
            'cart_total': float(cart.total_price) # Summary update ke liye
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

# =============================================
# CLEAR AND ADD TO CART API (Dynamic Switch)
# =============================================
@login_required
@require_POST
def clear_and_add_cart_api(request):
    try:
        data = json.loads(request.body)
        medicine_id = data.get('medicine_id')
        
        # 1. Safely remove active cart session items
        Cart.objects.filter(user=request.user, is_active=True).delete()
        
        # 2. Build pristine cart structure
        new_cart = Cart.objects.create(user=request.user, is_active=True)
        product = Medicine.objects.get(id=medicine_id)
        
        # 3. Inject new shop node item reference
        CartItem.objects.create(cart=new_cart, product=product, quantity=1)
        
        return JsonResponse({
            'success': True,
            'cart_count': 1,
            'message': "Your previous cart has been cleared successfully, and the new item has been added."
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

# =============================================
# Cart Page
# =============================================
@login_required
def view_cart(request):
    SHIPPING = 200
    cart_items = []
    total_price = 0
    cart_count = 0

    # ✅ FIX: is_active=True wali cart dhundho
    # Agar nahi mili to nayi bana do (get_or_create)
    cart, created = Cart.objects.get_or_create(
        user=request.user,
        is_active=True
    )

    if not created:  # Cart pehle se exist karti thi
        cart_items = CartItem.objects.filter(cart=cart).select_related('product')
        total_price = cart.total_price
        cart_count = cart.items.count()

    context = {
        'cart_items': cart_items,
        'total_price': total_price,
        'shipping': SHIPPING,
        'grand_total': total_price + SHIPPING,
        'cart_count': cart_count,
    }
    return render(request, "orders/cart.html", context)

# =============================================
# Checkout Page (GET — form dikhao)
# =============================================
def checkout(request):
    if not request.user.is_authenticated:
        return redirect('authentication:login_signup')

    try:
        # User ki active cart uthaein
        cart = Cart.objects.filter(user=request.user, is_active=True).first()
        if not cart:
            messages.error(request, "Your cart is empty.")
            return redirect('customers_d:search_medicines')
        cart_items = cart.items.all()
        
        subtotal = cart.total_price
        shipping = 200.0
        total = float(subtotal) + shipping

        # Role ke hisaab se base template
        if hasattr(request.user, 'role') and request.user.role == 'pharmacy':
            base = 'dashboards/pharmacy_base.html'
        else:
            base = 'customers_d/customer_base.html'
        
        context = {
            'cart_items': cart_items,
            'subtotal': subtotal,
            'shipping': shipping,
            'total': total,
            'total_amount_float': total,
            'base_template': base,
        }
        return render(request, "orders/checkout_page.html", context)
    except Cart.DoesNotExist:
        messages.error(request, "Your cart is empty. Please add items to your cart before checking out.")
        return redirect('customers_d:search_medicines')

# Place Order (POST — form submit)
# =============================================
@login_required
@transaction.atomic  # Taake agar koi error aaye toh database clean rahay
def place_order(request):
    from .payment_service import PaymentService
    payment_service = PaymentService()

    if request.method == 'POST':

        # 1. Form se data nikalna
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address', '')
        city = request.POST.get('city', '')
        province = request.POST.get('province', '')
        postal_code = request.POST.get('postal_code', '')
        payment_method = request.POST.get('payment_method')

        # 🌟 FIX: Notes field fetch karein form data se
        notes = request.POST.get('notes', '').strip()


        # Build full address from separate fields
        full_address_parts = [
            str(address).strip(),
            str(city).strip(),
            str(province).strip(),
            str(postal_code).strip(),
        ]
        full_address = ", ".join([p for p in full_address_parts if p]).strip()

        # 2. full_name combine karein
        full_name = f"{first_name} {last_name}".strip()
        if not full_name:
            full_name = request.user.get_full_name() or request.user.username

        try:
            # Safe filter use karein active cart uthane ke liye
            cart = Cart.objects.filter(user=request.user, is_active=True).first()
            if not cart:
                raise Cart.DoesNotExist
            cart_items = cart.items.all()
            
            if not cart_items:
                messages.error(request, "Your cart is empty. Please add items to your cart before checking out.")
                return redirect('customers_d:search_medicines')

            # 🌟 3. MULTI-VENDOR LOGIC: Cart ke pehle item se particular pharmacy identify karein
            first_item = cart_items.first()
            medicine_owner = first_item.product.user  # Medicine upload karne wala user (Pharmacy account)
            
            order_pharmacy = None
            if hasattr(medicine_owner, 'pharmacy'):
                order_pharmacy = medicine_owner.pharmacy  # Us user ki associated dynamic pharmacy profile

            shipping_fee = 200  
            final_total = float(cart.total_price) + shipping_fee

            # 4. Order Create karein (Ab pharmacy parameter ke sath)
            order = Order.objects.create(
                user=request.user,
                pharmacy=order_pharmacy,  # 👈 Particular pharmacy database mein save ho gayi!
                order_id='PH' + timezone.now().strftime('%Y%m%d%H%M%S'),
                full_name=full_name,
                email=email,
                phone=phone,
                address=full_address,
                total_amount=final_total,
                payment_method=payment_method,
                notes=notes,  # 🌟 FIX: Notes field pass karein
                status='Pending'
            )


            # 5. Order Items save karein (Cart se Order mein transfer) & Stock control update
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
                
                # 🔄 Real-time Stock check optimization aur subtraction logic
                if item.product.stock_quantity >= item.quantity:
                    item.product.stock_quantity -= item.quantity
                    item.product.save()

            # 6. PaymentService call (Missing feature: Payment record + payment_status)
            payment_result = payment_service.process_payment(
                order=order,
                gateway=payment_method,
                test_mode=True
            )

            # Update order.payment_status based on result and gateway rules
            if not payment_result.get('success'):
                order.payment_status = 'failed'
            else:
                # Architecture rule: COD stays unpaid until Delivered
                if payment_method == 'COD':
                    order.payment_status = 'unpaid'
                else:
                    order.payment_status = 'paid'

            order.save()
            request.session['payment_result'] = payment_result

            # 🔔 7. Real-time Dashboard Notification & Email safely triggered via dashboards utility

            if order_pharmacy and order_pharmacy.user:
                try:
                    from dashboards.utils import send_pharmacy_notification
                    
                    msg_content = f"New Order Received! Order ID: {order.order_id}. Total Amount: PKR {final_total}. Customer: {full_name}."
                    
                    # Naya clean utility function call jo sahi table use karega
                    send_pharmacy_notification(
                        pharmacy_user=order_pharmacy.user,
                        message=msg_content,
                        order=order
                    )
                    print(f"--> [SUCCESS] Core Notification & Email sent to Pharmacy: {order_pharmacy.user.username}")
                except Exception as notif_err:
                    print(f"--> [CRITICAL ERROR] Core Notification Engine failed: {notif_err}")
            else:
                print("--> [WARNING] order_pharmacy or order_pharmacy.user not found. Skipping notifications.")

            # 8. Cart ko deactivate/khali karein
            cart.items.all().delete()
            cart.is_active = False
            cart.save()

            # 9. Session mein ID save karein success page ke liye
            request.session['last_order_id'] = order.order_id
            
            messages.success(request, "Your order has been placed successfully!")
            return redirect('orders:order_success')

        except Cart.DoesNotExist:
            messages.error(request, "An active cart is required to place an order.")
            return redirect('customers_d:search_medicines')
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('orders:checkout')

    return redirect('orders:checkout')

# =============================================
# Order Success Page
# =============================================
def order_success(request):
    order_id = request.session.get('last_order_id')

    if not order_id:
        return redirect('customers_d:search_medicines')

    try:
        order = Order.objects.get(order_id=order_id)
        
        # Role ke hisaab se base template decide karein
        if hasattr(request.user, 'role') and request.user.role == 'pharmacy':
            base = 'dashboards/pharmacy_base.html'
        else:
            base = 'customers_d/customer_base.html'
        
        return render(request, "orders/order_success.html", {
            'order': order,
            'base_template': base,
        })
    except Order.DoesNotExist:
        return redirect('customers_d:search_medicines')