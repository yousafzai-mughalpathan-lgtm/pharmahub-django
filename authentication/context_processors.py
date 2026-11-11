# authentication/context_processors.py
from customers_d.models import Cart, CustomerNotification

def dynamic_base_template(request):
    """Determines which base template to use based on user role."""
    if not request.user.is_authenticated:
        return {'base_template': 'pharmacy/base.html'}
    
    role = getattr(request.user, 'role', None)
    
    if role == 'pharmacy':
        if request.user.is_verified_pharmacist:
            base = 'dashboards/base.html'  # Full Dashboard Base
        else:
            base = 'authentication/verification_base.html' # Limited Base for Unverified
    elif role == 'customer':
        base = 'customers_d/base.html'
    elif role == 'admin':
        base = 'admin_panel/base.html'
    else:
        base = 'pharmacy/base.html'
    
    return {'base_template': base}

def cart_count(request):
    count = 0
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.filter(user=request.user, is_active=True).first()
            count = cart.items_count if cart else 0
        except Exception:
            count = 0
    return {'global_cart_count': count}

def customer_notif_count(request):
    if request.user.is_authenticated:
        count = CustomerNotification.objects.filter(user=request.user, is_read=False).count()
        return {'customer_unread_count': count}
    return {'customer_unread_count': 0}