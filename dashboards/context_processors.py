# dashboards/context_processors.py
from dashboards.models import Pharmacy, PharmacyNotification  # Naya model add kiya
from customers_d.models import CustomerNotification          # Customer ka model add kiya

def pharmacy_context(request):
    if request.user.is_authenticated:
        pharmacy = Pharmacy.objects.filter(user=request.user).first()
        return {'pharmacy': pharmacy}
    return {}


def pharmacy_data(request):
    if request.user.is_authenticated:
        try:
            pharmacy = Pharmacy.objects.get(user=request.user)
            return {'pharmacy': pharmacy}
        except Pharmacy.DoesNotExist:
            return {'pharmacy': None}
    return {'pharmacy': None}


def pharmacy_notifications(request):
    """
    Yeh function har page par check karega ke current pharmacy user ki 
    kitni unread transactional notifications hain (Teal Dot ke liye).
    """
    if request.user.is_authenticated:
        # Naye PharmacyNotification table se filter lagaya
        count = PharmacyNotification.objects.filter(
            user=request.user, 
            is_read=False
        ).count()
        
        return {
            'pharmacy_notification_count': count
        }
    
    return {'pharmacy_notification_count': 0}


def customer_notifications_context(request):
    """
    Yeh function har page par check karega ke current customer user ki 
    kitni unread notifications hain.
    """
    if request.user.is_authenticated:
        # CustomerNotification table se filter lagaya
        count = CustomerNotification.objects.filter(
            user=request.user, 
            is_read=False
        ).count()
        
        return {
            'customer_notification_count': count
        }
    
    return {'customer_notification_count': 0}