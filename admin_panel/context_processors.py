from django.db.models import Q
from .models import Notification

def admin_notifications(request):
    if request.user.is_authenticated:
        # Sirf login user (Pharmacy) ki unread notifications count karein
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    else:
        count = 0

    context = {'notification_count': count}

    # Sidebar "Core Control" badge counts — sirf admin/super_admin ke liye query
    # karte hain taake customer/pharmacy pages pe extra DB hits na hon.
    if request.user.is_authenticated and getattr(request.user, 'role', None) in ('admin', 'super_admin'):
        from dashboards.models import Pharmacy
        from authentication.models import CustomUser

        context['pending_pharmacy_count'] = Pharmacy.objects.filter(
            verification_status='pending'
        ).count()

        if hasattr(CustomUser, 'is_verified_pharmacist'):
            pending_pharmacists = CustomUser.objects.filter(
                role='pharmacist', is_verified_pharmacist=False
            ).count()
        else:
            pending_pharmacists = CustomUser.objects.filter(role='pharmacist').count()
        context['pending_pharmacist_count'] = pending_pharmacists

    return context