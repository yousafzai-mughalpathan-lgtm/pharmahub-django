"""
PHARMAHUB - API Serializers
Django REST Framework Complete Serializers

REFACTOR NOTE (duplicate-model cleanup):
This file used to read/write the disconnected admin_panel.* duplicate
models (Pharmacy, Medicine, Order, OrderItem, Customer, Prescription).
Those tables are orphaned -- they are never touched by the real site
(checkout, pharmacy dashboard, customer dashboard). This version switches
every serializer to the LIVE models that the actual app uses:

    admin_panel.Pharmacy      -> dashboards.Pharmacy
    admin_panel.Medicine      -> dashboards.Medicine
    admin_panel.MedicineCategory -> (no live equivalent; derived from
                                     dashboards.Medicine.category strings)
    admin_panel.Order/OrderItem -> orders.Order / orders.OrderItem
    admin_panel.Customer      -> customers_d.Customer (+ computed fields)
    admin_panel.Prescription  -> customers_d.Prescription

No new migrations were added. Where the live model has fewer fields than
the old duplicate (e.g. Customer has no phone/address/lifetime_spent),
those fields are exposed as read-only computed values instead of being
dropped, so the admin UI keeps working without needing a schema change.

Untouched (still admin_panel.* on purpose, these are NOT duplicated
anywhere in the real app so there's nothing to unify):
    Notification, SystemSettings, SecurityLog, AdminActivityLog,
    LoginLog, PharmacyMedicineStock
"""

from decimal import Decimal
from django.db.models import Sum
from rest_framework import serializers
from django.contrib.auth import authenticate
# Import CustomUser from authentication app
from authentication.models import CustomUser

# ------------------------------------------------------------------
# Admin-only models that have no live counterpart elsewhere in the app
# (kept on admin_panel.models, nothing to migrate for these).
# ------------------------------------------------------------------
from .models import (
    Notification, SystemSettings, SecurityLog,
    AdminActivityLog, LoginLog, PharmacyMedicineStock,
)

# ------------------------------------------------------------------
# LIVE models (the real, connected schema used by the actual site)
# ------------------------------------------------------------------
from dashboards.models import Pharmacy, Medicine
from orders.models import Order, OrderItem, Payment
from customers_d.models import Customer, Prescription

# Real order-status vocabulary used across the app (orders/views.py,
# dashboards/views.py, customers_d/views.py). orders.Order.status is a
# free-text CharField, not a choices field, so we keep the valid set here
# instead of on the model.
ORDER_STATUS_VALUES = ['Pending', 'Approved', 'Rejected', 'Ready', 'Delivered', 'Cancelled']

# Real prescription status vocabulary (customers_d.Prescription.STATUS_CHOICES)
PRESCRIPTION_STATUS_VALUES = ['pending', 'approved', 'rejected']


# ============================================
# USER SERIALIZERS
# ============================================
class UserSerializer(serializers.ModelSerializer):
    """Complete User Serializer"""
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'license', 'is_active', 'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']

class UserLoginSerializer(serializers.Serializer):
    """Login Serializer"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(
            email=data['email'],
            password=data['password']
        )

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        if not user.is_active:
            raise serializers.ValidationError("Your account has been blocked")

        data['user'] = user
        return data


class AdminUserSerializer(serializers.ModelSerializer):
    """Serializer for admin to manage users"""
    password = serializers.CharField(write_only=True, required=False)
    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'username', 'role',
            'is_active', 'is_verified_pharmacist',
            'license', 'license_document', 'password'
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = CustomUser.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

class UserRegistrationSerializer(serializers.ModelSerializer):
    """User Registration"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'role', 'license'
        ]

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")

        if data.get('role') in ['pharmacy', 'pharmacist'] and not data.get('license'):
            raise serializers.ValidationError("License number is required for pharmacies and pharmacists")

        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = CustomUser.objects.create_user(
            password=password,
            **validated_data
        )
        return user

# ============================================
# PHARMACY SERIALIZERS  (dashboards.Pharmacy — live model)
# ============================================
class PharmacySerializer(serializers.ModelSerializer):
    """Complete Pharmacy Serializer"""
    user_details = UserSerializer(source='user', read_only=True)
    owner_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Pharmacy
        fields = '__all__'
        read_only_fields = [
            'submitted_at', 'verified_at'
        ]

class PharmacyListSerializer(serializers.ModelSerializer):
    """Pharmacy List (Minimal)"""
    owner_name = serializers.CharField(read_only=True)

    class Meta:
        model = Pharmacy
        fields = [
            'id', 'name', 'owner_name', 'city', 'verification_status',
            'is_verified', 'submitted_at'
        ]

class PharmacyRegistrationSerializer(serializers.Serializer):
    """Pharmacy Registration with User"""
    # User fields
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    license_number = serializers.CharField()

    # Pharmacy fields
    name = serializers.CharField()
    owner_name = serializers.CharField()
    phone = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    pin_code = serializers.CharField()
    gst_number = serializers.CharField()
    operating_hours = serializers.CharField()
    license_document = serializers.FileField(required=False)

    def create(self, validated_data):
        # Create user
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role='pharmacy',
            license=validated_data['license_number']
        )

        # Create pharmacy (dashboards.Pharmacy — same model the real
        # registration flow / admin verification queue uses)
        pharmacy = Pharmacy.objects.create(
            user=user,
            name=validated_data['name'],
            owner_name=validated_data['owner_name'],
            email=validated_data['email'],
            phone=validated_data['phone'],
            address=validated_data['address'],
            city=validated_data['city'],
            pin_code=validated_data['pin_code'],
            gst_number=validated_data['gst_number'],
            operating_hours=validated_data['operating_hours'],
            license_number=validated_data['license_number'],
            license_document=validated_data.get('license_document'),
        )

        return pharmacy

class PharmacyApprovalSerializer(serializers.Serializer):
    """Approve/Reject Pharmacy"""
    action = serializers.ChoiceField(choices=['approve', 'reject', 'suspend'])
    reason = serializers.CharField(required=False, allow_blank=True)

# ============================================
# CUSTOMER SERIALIZERS  (customers_d.Customer — live model)
#
# Live Customer only has `user` (OneToOne to CustomUser). There is no
# phone/address/location/total_orders/lifetime_spent/is_blocked column
# anywhere in the real schema, so instead of crashing (or silently
# dropping the admin feature) these are exposed as computed, read-only
# values:
#   - is_blocked      -> derived from CustomUser.is_active (this is
#                        already how login blocks work — see
#                        UserLoginSerializer above)
#   - total_orders     -> live count from orders.Order
#   - lifetime_spent   -> live sum of Delivered orders' total_amount
#   - phone/address/location -> not collected anywhere for customers
#                        (address is only captured per-order at
#                        checkout), so these are returned as null.
# ============================================
class CustomerSerializer(serializers.ModelSerializer):
    """Customer Serializer"""
    user_details = UserSerializer(source='user', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()
    lifetime_spent = serializers.SerializerMethodField()
    is_blocked = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'user', 'user_details', 'email', 'username', 'full_name',
            'phone', 'address', 'location',
            'total_orders', 'lifetime_spent', 'is_blocked',
        ]

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username

    def get_phone(self, obj):
        # Not collected on the real Customer profile (only per-order phone
        # exists on orders.Order). Left as null rather than guessed.
        return None

    def get_address(self, obj):
        # Same as phone: no persistent customer address in the live schema.
        return None

    def get_location(self, obj):
        return None

    def get_total_orders(self, obj):
        return Order.objects.filter(user=obj.user).count()

    def get_lifetime_spent(self, obj):
        total = Order.objects.filter(
            user=obj.user, status='Delivered'
        ).aggregate(Sum('total_amount'))['total_amount__sum']
        return total or 0

    def get_is_blocked(self, obj):
        return not obj.user.is_active

class CustomerListSerializer(serializers.ModelSerializer):
    """Customer List (Minimal)"""
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()
    lifetime_spent = serializers.SerializerMethodField()
    is_blocked = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'username', 'full_name', 'email',
            'total_orders', 'lifetime_spent', 'is_blocked', 'user'
        ]

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username

    def get_total_orders(self, obj):
        return Order.objects.filter(user=obj.user).count()

    def get_lifetime_spent(self, obj):
        total = Order.objects.filter(
            user=obj.user, status='Delivered'
        ).aggregate(Sum('total_amount'))['total_amount__sum']
        return total or 0

    def get_is_blocked(self, obj):
        return not obj.user.is_active

# ============================================
# MEDICINE SERIALIZERS  (dashboards.Medicine — live model)
#
# Live Medicine.category is a plain CharField (not a FK to a category
# table), and there's no prescription_type field. MedicineCategory has
# no live equivalent at all — categories are just distinct strings on
# Medicine — so category "objects" below are virtual (see
# MedicineCategorySerializer), not backed by a real model/table.
# ============================================
class MedicineCategorySerializer(serializers.Serializer):
    """
    Virtual medicine category — NOT backed by a database table.
    dashboards.Medicine.category is a free-text field, so a "category"
    here is just a distinct value of that field plus a live count.
    Read-only: there's nothing to create/update since it isn't a real
    model row.
    """
    name = serializers.CharField()
    medicine_count = serializers.IntegerField()

class MedicineSerializer(serializers.ModelSerializer):
    """Medicine Serializer"""
    pharmacy_name = serializers.CharField(source='pharmacy.name', read_only=True)
    category_name = serializers.CharField(source='category', read_only=True)

    class Meta:
        model = Medicine
        fields = '__all__'
        read_only_fields = ['created_at']

class MedicineListSerializer(serializers.ModelSerializer):
    """Medicine List — used by the admin Medicine Control panel (/api/medicines/).
    Must include every field admin_panel/templates/admin/medicine_control.html's
    JS reads off each row (medicine.image, medicine.brand, medicine.category,
    medicine.description, medicine.expiry_date, medicine.ban_reason) — leaving
    any of these out means the admin UI silently falls back to placeholders
    even when the pharmacy uploaded real data."""
    category_name = serializers.CharField(source='category', read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Medicine
        fields = [
            'id', 'name', 'brand', 'category', 'category_name',
            'description', 'price', 'stock_quantity', 'expiry_date',
            'is_banned', 'ban_reason', 'image',
        ]

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url

# ============================================
# PHARMACY MEDICINE STOCK SERIALIZERS
#
# NOT part of this refactor: admin_panel.PharmacyMedicineStock models a
# shared catalog where several pharmacies stock the same medicine at
# different prices. The live schema doesn't work that way — dashboards.
# Medicine already belongs to exactly one pharmacy with its own
# stock_quantity/price. There's no live table to switch this to without
# a real schema change, and it isn't wired to any URL/router endpoint,
# so it's left untouched rather than guessed at.
# ============================================
class PharmacyMedicineStockSerializer(serializers.ModelSerializer):
    """Pharmacy Stock Management"""
    pharmacy_name = serializers.CharField(source='pharmacy.name', read_only=True)
    medicine_name = serializers.CharField(source='medicine.name', read_only=True)

    class Meta:
        model = PharmacyMedicineStock
        fields = '__all__'
        read_only_fields = ['is_low_stock', 'created_at', 'updated_at']

class PharmacyMedicineStockListSerializer(serializers.ModelSerializer):
    """Stock List (Minimal)"""
    medicine_name = serializers.CharField(source='medicine.name', read_only=True)

    class Meta:
        model = PharmacyMedicineStock
        fields = [
            'id', 'medicine_name', 'stock_quantity', 'selling_price',
            'is_available', 'is_low_stock', 'expiry_date'
        ]

# ============================================
# ORDER SERIALIZERS  (orders.Order / orders.OrderItem — live models)
#
# Field-name differences from the old admin_panel duplicate:
#   customer FK          -> order.user  (direct CustomUser FK, no
#                            intermediate Customer row)
#   delivery_address      -> order.address
#   ORDER_STATUS choices  -> free-text status; real values are
#                            'Pending'/'Approved'/'Rejected'/'Ready'/
#                            'Delivered'/'Cancelled' (see
#                            ORDER_STATUS_VALUES above)
#   OrderItem.medicine    -> OrderItem.product
# ============================================
class OrderItemSerializer(serializers.ModelSerializer):
    """Order Item"""
    medicine_name = serializers.CharField(source='product.name', read_only=True)
    medicine_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)
    # OrderItem only stores `price` (unit price); admin templates expect
    # price_per_unit/total_price, so alias/compute them here instead of
    # leaving the frontend to read fields that don't exist.
    price_per_unit = serializers.DecimalField(source='price', max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = '__all__'

    def get_total_price(self, obj):
        return obj.get_total_item_price()

class OrderSerializer(serializers.ModelSerializer):
    """Complete Order Serializer"""
    items = OrderItemSerializer(many=True, read_only=True)
    customer_name = serializers.SerializerMethodField()
    pharmacy_name = serializers.CharField(source='pharmacy.name', read_only=True)
    delivery_address = serializers.CharField(source='address', read_only=True)
    # orders.Order has no subtotal/delivery_charges/discount fields — it
    # only stores the final total_amount. Provide subtotal as the sum of
    # item totals so the admin panel shows a real number instead of
    # reading a field that was never on the model.
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['order_id', 'created_at']

    def get_customer_name(self, obj):
        user = obj.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_subtotal(self, obj):
        return sum((item.get_total_item_price() for item in obj.items.all()), Decimal('0'))

class OrderListSerializer(serializers.ModelSerializer):
    """Order List (Minimal)"""
    customer_name = serializers.SerializerMethodField()
    pharmacy_name = serializers.CharField(source='pharmacy.name', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_id', 'customer_name', 'pharmacy_name',
            'total_amount', 'status', 'created_at'
        ]

    def get_customer_name(self, obj):
        user = obj.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

class OrderCreateSerializer(serializers.Serializer):
    """
    Create Order (admin/API path).

    NOTE: this is NOT the checkout flow — real customers place orders
    through orders/views.py::place_order (cart -> checkout form), which
    is untouched by this refactor. This serializer is only for the
    separate DRF endpoint (POST /api/orders/); it's rewritten to create
    real orders.Order/OrderItem rows instead of admin_panel duplicates.

    Request field names (pharmacy_id, delivery_address, items with
    medicine_id/quantity/price) are kept the same as before for
    backward compatibility with anything already calling this endpoint.
    """
    pharmacy_id = serializers.IntegerField()
    delivery_address = serializers.CharField()
    items = serializers.ListField(
        child=serializers.DictField()
    )

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Order must have at least one item")
        return value

    def create(self, validated_data):
        from django.db import transaction
        import uuid

        request = self.context['request']
        user = request.user

        with transaction.atomic():
            items_data = validated_data.pop('items')

            # Calculate total
            total = sum(
                item['quantity'] * item['price']
                for item in items_data
            )

            full_name = user.get_full_name() or user.username

            # Create order against the live Order model. Order links to the
            # customer via `user` directly (no Customer FK), and the address
            # field is called `address`, not `delivery_address`.
            order = Order.objects.create(
                order_id=f"ORD-{uuid.uuid4().hex[:8].upper()}",
                user=user,
                pharmacy_id=validated_data['pharmacy_id'],
                total_amount=total,
                address=validated_data['delivery_address'],
                email=getattr(user, 'email', '') or '',
                phone='',
                full_name=full_name,
                status='Pending',
            )

            # Create order items (OrderItem.product, not .medicine)
            for item_data in items_data:
                OrderItem.objects.create(
                    order=order,
                    product_id=item_data['medicine_id'],
                    quantity=item_data['quantity'],
                    price=item_data['price']
                )

            return order

# ============================================
# PRESCRIPTION SERIALIZERS  (customers_d.Prescription — live model)
#
# Field-name / vocabulary differences from the old admin_panel duplicate:
#   customer/pharmacy FKs -> straight to CustomUser (not to Customer/
#                            Pharmacy business-profile models)
#   image                 -> prescription_image
#   VERIFICATION_STATUS   -> real choices are only pending/approved/
#                            rejected (lowercase) — there is no
#                            separate FLAGGED state in the live model,
#                            so "flag" is mapped onto reject + reason
#                            (see PrescriptionVerifySerializer/flag()).
#   prescription_id       -> no such field; displayed as f"PRX-{id}",
#                            matching the convention already used in
#                            dashboards/views.py and customer templates.
#   verified_at/medicines_text -> don't exist on the live model.
# ============================================
class PrescriptionSerializer(serializers.ModelSerializer):
    """Prescription Serializer"""
    prescription_id = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    pharmacy_name = serializers.SerializerMethodField()
    image = serializers.ImageField(source='prescription_image', read_only=True)

    class Meta:
        model = Prescription
        fields = [
            'id', 'prescription_id', 'customer', 'pharmacy',
            'customer_name', 'pharmacy_name',
            'prescription_image', 'image', 'status',
            'rejection_reason', 'created_at',
        ]
        read_only_fields = ['created_at']

    def get_prescription_id(self, obj):
        return f"PRX-{obj.id}"

    def get_customer_name(self, obj):
        user = obj.customer
        return f"{user.first_name} {user.last_name}".strip() or user.username

    def get_pharmacy_name(self, obj):
        user = obj.pharmacy
        # obj.pharmacy is the pharmacy's CustomUser; the business profile
        # (name, etc.) lives on the related dashboards.Pharmacy, when it
        # exists.
        if hasattr(user, 'pharmacy'):
            return user.pharmacy.name
        return user.username

class PrescriptionVerifySerializer(serializers.Serializer):
    """
    Verify/Reject Prescription.

    The live Prescription model only supports pending/approved/rejected.
    'FLAGGED' isn't a real status, so a flag action is treated as a
    reject with a reason (rejection_reason), same as
    dashboards/views.py::reject_prescription already does.
    """
    action = serializers.ChoiceField(choices=['approved', 'rejected', 'flagged'])
    reason = serializers.CharField(required=False, allow_blank=True)

# ============================================
# PAYMENT SERIALIZERS  (orders.Payment — live model)
# ============================================
class PaymentSerializer(serializers.ModelSerializer):
    """Payment Serializer"""
    order_id = serializers.CharField(source='order.order_id', read_only=True)
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['created_at']

    def get_customer_name(self, obj):
        user = obj.order.user
        return f"{user.first_name} {user.last_name}".strip() or user.username

# ============================================
# NOTIFICATION SERIALIZERS  (admin_panel.Notification — no duplicate elsewhere)
# ============================================
class NotificationSerializer(serializers.ModelSerializer):
    """Notification Serializer"""

    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['created_at']

class NotificationCreateSerializer(serializers.ModelSerializer):
    """Create Notification"""
    class Meta:
        model = Notification
        fields = [
            'title', 'content', 'notification_type',
            'recipient_type', 'is_urgent', 'recipient'
        ]
        extra_kwargs = {'recipient': {'required': False, 'allow_null': True}}

# ============================================
# ADMIN ACTIVITY LOG SERIALIZERS
# ============================================
class AdminActivityLogSerializer(serializers.ModelSerializer):
    """Admin Activity Log"""
    admin_name = serializers.CharField(source='admin.username', read_only=True)
    admin_email = serializers.EmailField(source='admin.email', read_only=True)

    class Meta:
        model = AdminActivityLog
        fields = '__all__'
        read_only_fields = ['created_at']

class AdminActivityLogListSerializer(serializers.ModelSerializer):
    """Admin Activity List (Minimal)"""
    admin_name = serializers.CharField(source='admin.username', read_only=True)

    class Meta:
        model = AdminActivityLog
        fields = [
            'id', 'admin_name', 'action', 'target_model',
            'description', 'created_at'
        ]

# ============================================
# LOGIN LOG SERIALIZERS
# ============================================
class LoginLogSerializer(serializers.ModelSerializer):
    """Login Log"""
    username = serializers.CharField(source='user.username', read_only=True, allow_null=True)

    class Meta:
        model = LoginLog
        fields = '__all__'
        read_only_fields = ['created_at']

class LoginLogListSerializer(serializers.ModelSerializer):
    """Login Log List (Minimal)"""
    username = serializers.CharField(source='user.username', read_only=True, allow_null=True)

    class Meta:
        model = LoginLog
        fields = [
            'id', 'username', 'email_attempted', 'status',
            'ip_address', 'created_at'
        ]

# ============================================
# SECURITY LOG SERIALIZERS
# ============================================
class SecurityLogSerializer(serializers.ModelSerializer):
    """Security Log"""
    username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = SecurityLog
        fields = '__all__'
        read_only_fields = ['created_at']

# ============================================
# SYSTEM SETTINGS SERIALIZERS
# ============================================
class SystemSettingsSerializer(serializers.ModelSerializer):
    """System Settings"""

    class Meta:
        model = SystemSettings
        fields = '__all__'

# ============================================
# STATISTICS SERIALIZERS
# ============================================
class DashboardStatsSerializer(serializers.Serializer):
    """Dashboard Statistics"""
    total_pharmacies = serializers.IntegerField()
    verified_pharmacies = serializers.IntegerField()
    pending_pharmacies = serializers.IntegerField()
    suspended_pharmacies = serializers.IntegerField()
    total_customers = serializers.IntegerField()
    blocked_customers = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    completed_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    monthly_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_medicines = serializers.IntegerField()
    banned_medicines = serializers.IntegerField()
    low_stock_alerts = serializers.IntegerField()