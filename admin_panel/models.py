from django.db import models
from django.conf import settings

# 1. Pharmacy Model (Already exists - needs enhancement)
class Pharmacy(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,null=True, 
        blank=True, related_name='pharmacy_profile')
    name = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    location = models.CharField(max_length=255)
    license_number = models.CharField(max_length=100, unique=True)
    license_document = models.FileField(upload_to='licenses/', null=True, blank=True)
    
    # Status fields
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_suspended = models.BooleanField(default=False)
    
    # Performance metrics
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    monthly_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_orders = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Pharmacy'
        verbose_name_plural = 'Pharmacies'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name

# 2. Customer Model
class Customer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_profile')
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    
    # Customer metrics
    total_orders = models.IntegerField(default=0)
    lifetime_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Status
    is_blocked = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

# 3. Medicine Category
class MedicineCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon_class = models.CharField(max_length=50, default='fas fa-pills')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Medicine Category'
        verbose_name_plural = 'Medicine Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name

# 4. Medicine Model
class Medicine(models.Model):
    PRESCRIPTION_CHOICES = [
        ('REQUIRED', 'Prescription Required'),
        ('OTC', 'Over The Counter'),
    ]
    
    name = models.CharField(max_length=255)
    category = models.ForeignKey(MedicineCategory, on_delete=models.SET_NULL, null=True, related_name='medicines')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    prescription_type = models.CharField(max_length=20, choices=PRESCRIPTION_CHOICES, default='OTC')
    is_banned = models.BooleanField(default=False)
    ban_reason = models.TextField(blank=True)
    
    # Pharmacy relation
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='medicines')
    
    # Stock
    stock_quantity = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Medicine'
        verbose_name_plural = 'Medicines'
        ordering = ['name']
    
    def __str__(self):
        return self.name

# 5. Order Model
class Order(models.Model):
    ORDER_STATUS = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    order_id = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='orders')
    
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='PENDING')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    delivery_address = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.order_id

# 6. Order Item
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.medicine.name} x {self.quantity}"

# 7. Prescription Model
class Prescription(models.Model):
    VERIFICATION_STATUS = [
        ('PENDING', 'Pending Review'),
        ('VERIFIED', 'Verified'),
        ('FLAGGED', 'Flagged'),
        ('REJECTED', 'Rejected'),
    ]
    
    prescription_id = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='prescriptions')
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.SET_NULL, null=True, related_name='prescriptions')
    
    image = models.ImageField(upload_to='prescriptions/')
    status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='PENDING')
    
    # Medicines extracted from prescription
    medicines_text = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Prescription'
        verbose_name_plural = 'Prescriptions'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.prescription_id

# 8. Payment Model
class Payment(models.Model):
    PAYMENT_STATUS = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    
    transaction_id = models.CharField(max_length=50, unique=True)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='PENDING')
    
    created_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.transaction_id

# 9. Notification Model
from django.db import models
from django.conf import settings

# 9. Notification Model
class Notification(models.Model):
    RECIPIENT_TYPES = [
        ('ALL', 'All Users'),
        ('CUSTOMERS', 'All Customers'),
        ('PHARMACIES', 'All Pharmacies'),
        ('VERIFIED_PHARMACIES', 'Verified Pharmacies'),
        ('SPECIFIC', 'Specific User'),
    ]
    
    NOTIFICATION_TYPES = [
        ('ANNOUNCEMENT', 'Announcement'),
        ('WARNING', 'Warning'),
        ('POLICY', 'Policy Update'),
        ('MAINTENANCE', 'Maintenance'),
    ]
    
    # Nayi Field: Jo makhsoos bande ko track karegi (Specific User ke liye)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='notifications'
    )
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    recipient_type = models.CharField(max_length=30, choices=RECIPIENT_TYPES)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    is_urgent = models.BooleanField(default=False)
    
    # Nayi Field: Taake parhi hui notifications ka count khatam ho sakay
    is_read = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.recipient_type}"

# 10. System Settings
class SystemSettings(models.Model):
    platform_name = models.CharField(max_length=100, default='PharmaHub')
    support_email = models.EmailField(default='support@pharmahub.com')
    support_phone = models.CharField(max_length=20, default='+92-XXX-XXXXXXX')
    platform_version = models.CharField(max_length=20, default='1.0.0')
    
    # Verification settings
    auto_verify_license = models.BooleanField(default=False)
    manual_review_required = models.BooleanField(default=True)
    license_validity_days = models.IntegerField(default=365)
    
    # Financial settings
    platform_commission = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    
    # Terms & Policies
    terms_and_conditions = models.TextField(blank=True)
    privacy_policy = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and SystemSettings.objects.exists():
            raise ValueError('SystemSettings instance already exists')
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return self.platform_name

# 11. Security Log
class SecurityLog(models.Model):
    ACTION_TYPES = [
        ('LOGIN_SUCCESS', 'Login Success'),
        ('LOGIN_FAILED', 'Login Failed'),
        ('PASSWORD_CHANGED', 'Password Changed'),
        ('PHARMACY_APPROVED', 'Pharmacy Approved'),
        ('PHARMACY_SUSPENDED', 'Pharmacy Suspended'),
        ('CUSTOMER_BLOCKED', 'Customer Blocked'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50, choices=ACTION_TYPES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Security Log'
        verbose_name_plural = 'Security Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.action} - {self.user}"

# ============================================
# ✅ NEW MODELS ADDED BELOW
# ============================================

# 12. Admin Activity Log
class AdminActivityLog(models.Model):
    """Track all admin actions for audit purposes"""
    ACTION_CHOICES = [
        ('PHARMACY_APPROVED', 'Pharmacy Approved'),
        ('PHARMACY_REJECTED', 'Pharmacy Rejected'),
        ('PHARMACY_SUSPENDED', 'Pharmacy Suspended'),
        ('PHARMACY_REACTIVATED', 'Pharmacy Reactivated'),
        ('CUSTOMER_BLOCKED', 'Customer Blocked'),
        ('CUSTOMER_UNBLOCKED', 'Customer Unblocked'),
        ('MEDICINE_BANNED', 'Medicine Banned'),
        ('MEDICINE_UNBANNED', 'Medicine Unbanned'),
        ('ORDER_CANCELLED', 'Order Cancelled'),
        ('PRESCRIPTION_VERIFIED', 'Prescription Verified'),
        ('PRESCRIPTION_REJECTED', 'Prescription Rejected'),
        ('USER_ROLE_CHANGED', 'User Role Changed'),
        ('USER_ENABLED', 'User Enabled'),
        ('USER_DISABLED', 'User Disabled'),
        ('SETTINGS_UPDATED', 'Settings Updated'),
        ('NOTIFICATION_SENT', 'Notification Sent'),
        ('PAYMENTS_EXPORTED', 'Payments Report Exported'),
        ('REPORT_EXPORTED', 'Analytics Report Exported'),
        ('SECURITY_LOGS_EXPORTED', 'Security Logs Exported'),
        ('SETTINGS_UPDATE_FAILED', 'Settings Update Failed Validation'),
    ]

    
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                            null=True, related_name='admin_activities')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    target_model = models.CharField(max_length=50, blank=True)  # e.g., 'Pharmacy', 'Customer'
    target_id = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Admin Activity Log'
        verbose_name_plural = 'Admin Activity Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.admin.username if self.admin else 'Unknown'} - {self.action}"

# 13. Login Log
class LoginLog(models.Model):
    """Track all login attempts"""
    LOGIN_STATUS = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('BLOCKED', 'Blocked Account'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                           null=True, blank=True, related_name='login_logs')
    # allow null/blank so faulty login attempts don't break the log
    email_attempted = models.EmailField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=LOGIN_STATUS)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    device_info = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)  # City, Country
    failure_reason = models.CharField(max_length=200, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Login Log'
        verbose_name_plural = 'Login Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.email_attempted} - {self.status} - {self.created_at}"

# 14. Pharmacy Medicine Stock
class PharmacyMedicineStock(models.Model):
    """Track individual pharmacy's stock of medicines"""
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='medicine_stocks')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='pharmacy_stocks')
    
    # Stock details
    stock_quantity = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)  # Alert when stock falls below this
    max_stock_level = models.IntegerField(default=1000)
    
    # Pricing (pharmacy can set their own price)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Stock tracking
    last_restocked = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    batch_number = models.CharField(max_length=100, blank=True)
    
    # Status
    is_available = models.BooleanField(default=True)
    is_low_stock = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Pharmacy Medicine Stock'
        verbose_name_plural = 'Pharmacy Medicine Stocks'
        unique_together = ['pharmacy', 'medicine']  # Each pharmacy-medicine combo is unique
        ordering = ['-updated_at']
    
    def save(self, *args, **kwargs):
        # Auto-set low stock flag
        self.is_low_stock = self.stock_quantity <= self.reorder_level
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.pharmacy.name} - {self.medicine.name} (Stock: {self.stock_quantity})"