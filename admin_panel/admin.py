from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import (
    Pharmacy, Customer, Medicine, MedicineCategory,
    Order, OrderItem, Prescription, Payment,
    Notification, SystemSettings, SecurityLog
)

@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner_name', 'license_number', 'is_verified', 'is_active', 'rating']
    list_filter = ['is_verified', 'is_active', 'created_at']
    search_fields = ['name', 'owner_name', 'license_number']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'total_orders', 'lifetime_spent', 'is_blocked']
    list_filter = ['is_blocked', 'created_at']
    search_fields = ['user__username', 'user__email', 'phone']

@admin.register(MedicineCategory)
class MedicineCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'pharmacy', 'price', 'prescription_type', 'is_banned']
    list_filter = ['category', 'prescription_type', 'is_banned']
    search_fields = ['name']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'customer', 'pharmacy', 'status', 'total_amount', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['order_id']

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ['prescription_id', 'customer', 'pharmacy', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['prescription_id']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'order', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['transaction_id']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipient_type', 'notification_type', 'is_urgent', 'created_at']
    list_filter = ['recipient_type', 'notification_type', 'is_urgent']

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['platform_name', 'support_email', 'platform_version']

@admin.register(SecurityLog)
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'ip_address', 'created_at']
    list_filter = ['action', 'created_at']
    readonly_fields = ['created_at']
