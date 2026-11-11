from django.db import models
from django.conf import settings
# REMOVE: from dashboards.models import Medicine 
# (Circular import se bachne ke liye hum string 'dashboards.Medicine' use karein ge)

class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_carts')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Cart - {self.user.username}"

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def items_count(self):
        return sum(item.quantity for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    # Use string to avoid circular import
    product = models.ForeignKey('dashboards.Medicine', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def total_price(self):
        return self.quantity * self.product.price

class Customer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='customer'
    )

class Prescription(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_prescriptions')
    pharmacy = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pharmacy_prescriptions')
    prescription_image = models.ImageField(upload_to='prescriptions/')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prescription {self.id} - {self.customer.username}"

class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='items')
    # FIX: Changed 'Product' to 'dashboards.Medicine'
    product = models.ForeignKey('dashboards.Medicine', on_delete=models.CASCADE) 
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.product.name} (Qty: {self.quantity})"

class QuoteItem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='quote_items')
    medicine = models.ForeignKey('dashboards.Medicine', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price_at_quote = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.medicine.name} for PRX-{self.prescription.id}"

class CustomerNotification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    prescription = models.ForeignKey('Prescription', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']