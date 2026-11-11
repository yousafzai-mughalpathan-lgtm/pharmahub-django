
# dashboards/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
# dashboards/views.py mein:
from admin_panel.models import Notification


class Pharmacy(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='pharmacy'
    )

    name = models.CharField(max_length=200)
    owner_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=50)

    address = models.TextField()
    city = models.CharField(max_length=100)
    pin_code = models.CharField(max_length=20)

    # ✅ Geo fields for “Nearby” sorting + map markers
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)


    license_number = models.CharField(max_length=100)
    gst_number = models.CharField(max_length=100)

    operating_hours = models.CharField(max_length=100)
    services = models.JSONField(default=list, blank=True)

    logo = models.ImageField(upload_to='pharmacy_logos/', blank=True, null=True)
    license_document = models.FileField(upload_to='licenses/', null=True, blank=True)
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    verification_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    rejection_reason = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    # -----------------------------------

    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class Medicine(models.Model):

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='medicines', null=True) 

    name = models.CharField(max_length=100)
    brand = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    # ✅ Global-ish (per pharmacy) availability flags
    is_banned = models.BooleanField(default=False)
    ban_reason = models.TextField(blank=True)

    stock_quantity = models.IntegerField(default=0)
    expiry_date = models.DateField()
    batch_number = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='medicines/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name






class PharmacyNotification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pharmacy_notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    
    # String references taake circular import ka masla na aaye
    prescription = models.ForeignKey('customers_d.Prescription', on_delete=models.SET_NULL, null=True, blank=True)
    # Agar aap ki order app ka naam 'orders' aur model 'Order' h to yeh line perfect h:
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True) 
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Pharmacy Notif - {self.user.username} - {self.message[:20]}"