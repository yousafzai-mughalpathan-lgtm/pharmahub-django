# pharmacy/context_processors.py

from .models import Cart

def cart_count(request):
    """Add cart count to all templates"""
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user, is_active=True).first()
        cart_count = cart.items_count if cart else 0
    else:
        cart_count = 0
    
    return {'global_cart_count': cart_count}

from .models import CustomerNotification

def customer_notif_count(request):
    if request.user.is_authenticated:
        # Customer ki unread notifications ka count
        count = CustomerNotification.objects.filter(user=request.user, is_read=False).count()
        return {'customer_unread_count': count}
    return {'customer_unread_count': 0}