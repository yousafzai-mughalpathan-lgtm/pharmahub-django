"""
PHARMAHUB - Complete Models
API-Ready with Django REST Framework
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

# ============================================
# STEP 1: CUSTOM USER MODEL (FOUNDATION)
# ============================================
class User(AbstractUser):
    """
    Custom User Model - Foundation for entire system
    Used with JWT Authentication
    """
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('admin', 'Admin'),
        ('pharmacist', 'Pharmacist'),
        ('customer', 'Customer'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending Approval'),
        ('blocked', 'Blocked'),
        ('suspended', 'Suspended'),
    ]
    
    # Role & Status
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Contact
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Profile
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    
    # Security Tracking
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    failed_login_attempts = models.IntegerField(default=0)
    last_failed_login = models.DateTimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def is_admin_user(self):
        return self.role in ['super_admin', 'admin']
    
    @property
    def is_pharmacist_user(self):
        return self.role == 'pharmacist'
    
    @property
    def is_customer_user(self):
        return self.role == 'customer'

# ============================================
# STEP 2: PHARMACY MODEL
# ============================================
class Pharmacy(models.Model):
    """Pharmacy Profile with License Management"""
    
    VERIFICATION_STATUS = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    # User Link
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='pharmacy_profile'
    )
    
    # Basic Info
    pharmacy_name = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    
    # Location
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # License
    license_number = models.CharField(max_length=100, unique=True)
    license_document = models.FileField(upload_to='pharmacy_licenses/')
    license_expiry = models.DateField()
    
    # Verification
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default='pending'
    )
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_pharmacies'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=False)  # Active only after approval
    is_suspended = models.BooleanField(default=False)
    suspension_reason = models.TextField(blank=True, null=True)
    
    # Business Metrics
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    total_orders = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    monthly_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Settings
    accepts_online_orders = models.BooleanField(default=True)
    delivery_available = models.BooleanField(default=False)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pharmacies'
        verbose_name_plural = 'Pharmacies'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.pharmacy_name
    
    def approve(self, admin_user):
        """Approve pharmacy"""
        self.verification_status = 'approved'
        self.verified_by = admin_user
        self.verified_at = timezone.now()
        self.is_active = True
        self.user.status = 'active'
        self.user.save()
        self.save()
    
    def reject(self, admin_user, reason):
        """Reject pharmacy"""
        self.verification_status = 'rejected'
        self.verified_by = admin_user
        self.verified_at = timezone.now()
        self.rejection_reason = reason
        self.user.status = 'blocked'
        self.user.save()
        self.save()
    
    def suspend(self, reason):
        """Suspend pharmacy"""
        self.is_suspended = True
        self.is_active = False
        self.suspension_reason = reason
        self.save()

# ============================================
# STEP 3: CUSTOMER MODEL
# ============================================
class Customer(models.Model):
    """Customer Profile"""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='customer_profile'
    )
    
    # Personal Info
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    date_of_birth = models.DateField(null=True, blank=True)
    
    # Default Address
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    
    # Purchase History
    total_orders = models.IntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    lifetime_value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    last_order_date = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_blocked = models.BooleanField(default=False)
    block_reason = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customers'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.full_name
    
    def block(self, reason):
        """Block customer"""
        self.is_blocked = True
        self.block_reason = reason
        self.user.status = 'blocked'
        self.user.save()
        self.save()
    
    def unblock(self):
        """Unblock customer"""
        self.is_blocked = False
        self.block_reason = None
        self.user.status = 'active'
        self.user.save()
        self.save()

# ============================================
# STEP 4: MEDICINE MODELS
# ============================================
class MedicineCategory(models.Model):
    """Medicine Categories"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'medicine_categories'
        verbose_name_plural = 'Medicine Categories'
    
    def __str__(self):
        return self.name

class Medicine(models.Model):
    """Medicine Master Database"""
    
    PRESCRIPTION_TYPE = [
        ('required', 'Prescription Required'),
        ('not_required', 'No Prescription'),
    ]
    
    # Basic Info
    name = models.CharField(max_length=255)
    generic_name = models.CharField(max_length=255, blank=True)
    category = models.ForeignKey(MedicineCategory, on_delete=models.CASCADE)
    manufacturer = models.CharField(max_length=255)
    description = models.TextField()
    
    # Prescription
    prescription_type = models.CharField(max_length=20, choices=PRESCRIPTION_TYPE)
    
    # Pricing
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Stock (global reference, actual stock at pharmacy level)
    total_stock_available = models.IntegerField(default=0)
    
    # Control
    is_banned = models.BooleanField(default=False)
    ban_reason = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'medicines'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.manufacturer}"

class PharmacyMedicineStock(models.Model):
    """Individual Pharmacy's Medicine Stock"""
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE)
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    stock_quantity = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    last_restocked = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pharmacy_medicine_stock'
        unique_together = ['pharmacy', 'medicine']
    
    def __str__(self):
        return f"{self.pharmacy.pharmacy_name} - {self.medicine.name}"

# ============================================
# STEP 5: ORDER MODELS
# ============================================
class Order(models.Model):
    """Customer Orders"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('ready', 'Ready for Pickup'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    # Order ID
    order_id = models.CharField(max_length=50, unique=True)
    
    # Relations
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status
    order_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Delivery
    delivery_address = models.TextField()
    delivery_phone = models.CharField(max_length=15)
    
    # Notes
    customer_notes = models.TextField(blank=True)
    pharmacy_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.order_id
    
    def save(self, *args, **kwargs):
        # Auto-generate order_id
        if not self.order_id:
            import random
            self.order_id = f"ORD-{timezone.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        super().save(*args, **kwargs)

class OrderItem(models.Model):
    """Individual items in an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'order_items'
    
    def __str__(self):
        return f"{self.order.order_id} - {self.medicine.name}"
    
    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.price_per_unit
        super().save(*args, **kwargs)

# ============================================
# STEP 6: PRESCRIPTION MODEL
# ============================================
class Prescription(models.Model):
    """Prescription Management"""
    
    VERIFICATION_STATUS = [
        ('pending', 'Pending Review'),
        ('verified', 'Verified'),
        ('flagged', 'Flagged'),
        ('rejected', 'Rejected'),
    ]
    
    prescription_id = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)
    
    # Document
    document = models.FileField(upload_to='prescriptions/')
    
    # Verification
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default='pending'
    )
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_prescriptions'
    )
    flag_reason = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'prescriptions'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.prescription_id
    
    def save(self, *args, **kwargs):
        if not self.prescription_id:
            import random
            self.prescription_id = f"PRX-{timezone.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        super().save(*args, **kwargs)

# ============================================
# STEP 7: PAYMENT MODEL
# ============================================
class Payment(models.Model):
    """Payment Transactions"""
    
    PAYMENT_METHOD = [
        ('cod', 'Cash on Delivery'),
        ('online', 'Online Payment'),
        ('card', 'Card'),
        ('upi', 'UPI'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    transaction_id = models.CharField(max_length=100, unique=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Gateway Response
    gateway_response = models.JSONField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.transaction_id

# ============================================
# STEP 8: NOTIFICATION MODEL
# ============================================
class Notification(models.Model):
    """Platform Notifications"""
    
    NOTIFICATION_TYPE = [
        ('announcement', 'Announcement'),
        ('warning', 'Warning'),
        ('policy', 'Policy Update'),
        ('maintenance', 'Maintenance'),
    ]
    
    RECIPIENT_TYPE = [
        ('all', 'All Users'),
        ('customers', 'All Customers'),
        ('pharmacies', 'All Pharmacies'),
        ('verified_pharmacies', 'Verified Pharmacies'),
        ('specific', 'Specific User'),
    ]
    
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE)
    recipient_type = models.CharField(max_length=30, choices=RECIPIENT_TYPE)
    recipient_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications_received'
    )
    
    is_urgent = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    
    sent_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_sent')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title

# ============================================
# STEP 9: ADMIN ACTIVITY LOG
# ============================================
class AdminActivityLog(models.Model):
    """Admin Action Logging"""
    
    ACTION_CHOICES = [
        ('pharmacy_approved', 'Pharmacy Approved'),
        ('pharmacy_rejected', 'Pharmacy Rejected'),
        ('pharmacy_suspended', 'Pharmacy Suspended'),
        ('customer_blocked', 'Customer Blocked'),
        ('medicine_banned', 'Medicine Banned'),
        ('prescription_verified', 'Prescription Verified'),
        ('settings_updated', 'Settings Updated'),
    ]
    
    admin = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=50)
    target_id = models.IntegerField()
    description = models.TextField()
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'admin_activity_logs'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.admin.username} - {self.action}"

# ============================================
# STEP 10: LOGIN LOG
# ============================================
class LoginLog(models.Model):
    """Login Attempt Tracking"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    username_attempted = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    status = models.CharField(max_length=20)  # success, failed
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'login_logs'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.username_attempted} - {self.status}"

# ============================================
# STEP 11: SYSTEM SETTINGS
# ============================================
class SystemSettings(models.Model):
    """Platform Settings"""
    
    # Platform Info
    platform_name = models.CharField(max_length=100, default='PharmaHub')
    support_email = models.EmailField()
    support_phone = models.CharField(max_length=20)
    platform_version = models.CharField(max_length=20, default='1.0.0')
    
    # Verification
    auto_verify_enabled = models.BooleanField(default=False)
    manual_review_required = models.BooleanField(default=True)
    license_validity_days = models.IntegerField(default=365)
    
    # Business
    platform_commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00
    )
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    
    # Legal
    terms_and_conditions = models.TextField()
    privacy_policy = models.TextField()
    
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'system_settings'
        verbose_name_plural = 'System Settings'
    
    def __str__(self):
        return f"Settings - {self.platform_name}"

# ============================================
# SIGNALS
# ============================================
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create profile based on role"""
    if created:
        if instance.role == 'pharmacist':
            # Pharmacy profile will be created during registration
            pass
        elif instance.role == 'customer':
            Customer.objects.create(
                user=instance,
                full_name=instance.get_full_name() or instance.username,
                email=instance.email,
                phone=instance.phone or ''
            )
