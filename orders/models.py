from django.db import models
from django.conf import settings
from dashboards.models import Medicine
from dashboards.models import Pharmacy

class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    order_id = models.CharField(max_length=100, unique=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='Cash on Delivery')

    # Missing feature: payment status (paid/unpaid/failed) so templates can show it.
    payment_status = models.CharField(
        max_length=20,
        choices=[('unpaid', 'Unpaid'), ('paid', 'Paid'), ('failed', 'Failed')],
        default='unpaid'
    )

    # Missing feature: order notes shown in templates.
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='Pending')


    def __str__(self):
        return self.order_id

# orders/models.py mein
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    product = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def get_total_item_price(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"


class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    gateway = models.CharField(max_length=50)
    transaction_id = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('success', 'Success'), ('failed', 'Failed')],
        default='pending'
    )
    response_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.gateway} | {self.order.order_id} | {self.status}"

