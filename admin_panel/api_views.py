"""
PHARMAHUB - API Views
Complete REST API with JWT Authentication

REFACTOR NOTE: see the header comment in serializers.py. Every ViewSet
below now queries the LIVE models (dashboards.Pharmacy, dashboards.Medicine,
orders.Order/OrderItem/Payment, customers_d.Customer/Prescription) instead
of the disconnected admin_panel.* duplicates, so admin actions (approve,
block, ban, verify...) actually affect the same rows the real
checkout/pharmacy/customer flows read and write.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.core.mail import send_mail
from datetime import timedelta
from authentication.models import CustomUser
import logging

# Admin-only models with no live counterpart elsewhere
from .models import Notification, SystemSettings, SecurityLog, AdminActivityLog, LoginLog, PharmacyMedicineStock

# Live models
from dashboards.models import Pharmacy, Medicine
from orders.models import Order, OrderItem, Payment
from customers_d.models import Customer, Prescription

from .serializers import *
from .permissions import IsAdminUser, IsPharmacist, IsCustomer

logger = logging.getLogger(__name__)

# Helper function
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# ============================================
# AUTHENTICATION VIEWS
# ============================================
class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT Token with user details"""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            # Get user
            serializer = UserLoginSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.validated_data['user']

                # Log successful login
                LoginLog.objects.create(
                    user=user,
                    email_attempted=request.data.get('email', ''),
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    status='SUCCESS'
                )

                # Update user - use defensive attribute access in case migrations not applied
                try:
                    if hasattr(user, 'last_login_ip'):
                        user.last_login_ip = get_client_ip(request)
                    if hasattr(user, 'failed_login_attempts'):
                        user.failed_login_attempts = 0
                    user.save()
                except Exception:
                    # If saving fails (missing fields / DB mismatch), log and continue
                    pass

                # Add user details to response
                response.data['user'] = UserSerializer(user).data
        else:
            # Log failed login
            LoginLog.objects.create(
                email_attempted=request.data.get('email', ''),
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                status='FAILED'
            )

        return response

class UserRegistrationView(APIView):
    """User Registration"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Generate tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PharmacyRegistrationView(APIView):
    """Pharmacy Registration"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PharmacyRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            pharmacy = serializer.save()
            return Response({
                'message': 'Registration successful. Awaiting admin approval.',
                'pharmacy': PharmacySerializer(pharmacy).data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ============================================
# ADMIN VIEWS
# ============================================
class DashboardStatsView(APIView):
    """Admin Dashboard Statistics"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Pharmacy Stats (dashboards.Pharmacy)
        total_pharmacies = Pharmacy.objects.count()
        verified_pharmacies = Pharmacy.objects.filter(is_verified=True).count()
        pending_pharmacies = Pharmacy.objects.filter(verification_status='pending').count()
        suspended_pharmacies = Pharmacy.objects.filter(verification_status='rejected', is_verified=False).count()

        # Customer Stats (customers_d.Customer; "blocked" = CustomUser.is_active == False)
        total_customers = Customer.objects.count()
        blocked_customers = Customer.objects.filter(user__is_active=False).count()

        # Order Stats (orders.Order; real status values are Title Case)
        total_orders = Order.objects.count()
        pending_orders = Order.objects.filter(status='Pending').count()
        completed_orders = Order.objects.filter(status='Delivered').count()
        cancelled_orders = Order.objects.filter(status='Cancelled').count()

        # Revenue
        total_revenue = Order.objects.filter(
            status='Delivered'
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0

        monthly_revenue = Order.objects.filter(
            status='Delivered',
            created_at__gte=timezone.now() - timedelta(days=30)
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0

        # Medicine stats (dashboards.Medicine)
        total_medicines = Medicine.objects.count()
        banned_medicines = Medicine.objects.filter(is_banned=True).count()
        low_stock_alerts = Medicine.objects.filter(stock_quantity__lte=10).count()

        # City Distribution
        city_stats = Pharmacy.objects.values('city').annotate(
            count=Count('id')
        ).order_by('-count')[:5]

        stats = {
            'pharmacies': {
                'total': total_pharmacies,
                'verified': verified_pharmacies,
                'pending': pending_pharmacies,
                'suspended': suspended_pharmacies,
            },
            'customers': {
                'total': total_customers,
                'blocked': blocked_customers,
                'active': total_customers - blocked_customers,
            },
            'orders': {
                'total': total_orders,
                'pending': pending_orders,
                'completed': completed_orders,
                'cancelled': cancelled_orders,
            },
            'revenue': {
                'total': float(total_revenue),
                'monthly': float(monthly_revenue),
            },
            'medicines': {
                'total': total_medicines,
                'banned': banned_medicines,
                'low_stock': low_stock_alerts,
            },
            'city_distribution': list(city_stats)
        }

        return Response(stats)

# ============================================
# PHARMACY VIEWSETS  (dashboards.Pharmacy)
# ============================================
class PharmacyViewSet(viewsets.ModelViewSet):
    """Pharmacy CRUD + Admin Actions"""
    queryset = Pharmacy.objects.all()
    serializer_class = PharmacySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        queryset = Pharmacy.objects.all()

        # Filters
        status_filter = self.request.query_params.get('status')
        if status_filter == 'approved':
            queryset = queryset.filter(verification_status='approved', is_verified=True)
        elif status_filter == 'pending':
            queryset = queryset.filter(verification_status='pending', is_verified=False)
        elif status_filter == 'suspended':
            queryset = queryset.filter(verification_status='rejected', is_verified=False)

        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(owner_name__icontains=search) |
                Q(license_number__icontains=search)
            )

        return queryset

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve pharmacy"""
        pharmacy = self.get_object()
        pharmacy.is_verified = True
        pharmacy.verification_status = 'approved'
        pharmacy.verified_at = timezone.now()
        pharmacy.save()

        # Log action
        AdminActivityLog.objects.create(
            admin=request.user,
            action='PHARMACY_APPROVED',
            target_model='Pharmacy',
            target_id=pharmacy.id,
            description=f"Approved {pharmacy.name}",
            ip_address=get_client_ip(request)
        )

        # send email notification
        try:
            send_mail(
                subject='Your pharmacy has been approved',
                message=(
                    f"Dear {pharmacy.owner_name},\n\n"
                    f"Your pharmacy '{pharmacy.name}' is now live on PharmaHub. You may start "
                    "receiving orders immediately.\n\n"
                    "Regards,\nPharmaHub Team"
                ),
                from_email=None,
                recipient_list=[pharmacy.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception('Failed to send approval email to %s', pharmacy.email)

        return Response({
            'message': 'Pharmacy approved successfully',
            'pharmacy': PharmacySerializer(pharmacy).data
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject pharmacy"""
        pharmacy = self.get_object()
        pharmacy.is_verified = False
        pharmacy.verification_status = 'rejected'
        pharmacy.rejection_reason = request.data.get('reason', '')
        pharmacy.save()

        # Log action
        AdminActivityLog.objects.create(
            admin=request.user,
            action='PHARMACY_REJECTED',
            target_model='Pharmacy',
            target_id=pharmacy.id,
            description=f"Rejected {pharmacy.name}",
            ip_address=get_client_ip(request)
        )

        # send rejection email
        try:
            send_mail(
                subject='Pharmacy request declined',
                message=(
                    f"Dear {pharmacy.owner_name},\n\n"
                    "We reviewed your pharmacy submission and unfortunately cannot approve it at this time. "
                    "Please verify your documents and try again or contact support for help.\n\n"
                    "Regards,\nPharmaHub Team"
                ),
                from_email=None,
                recipient_list=[pharmacy.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception('Failed to send rejection email to %s', pharmacy.email)

        return Response({
            'message': 'Pharmacy rejected',
            'pharmacy': PharmacySerializer(pharmacy).data
        })

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        """Suspend pharmacy"""
        pharmacy = self.get_object()
        # dashboards.Pharmacy has no dedicated "suspended" state; mirror the
        # convention used by admin_panel/views.py::suspend_pharmacy so the API
        # and the real admin UI stay consistent.
        pharmacy.is_verified = False
        pharmacy.verification_status = 'rejected'
        pharmacy.rejection_reason = request.data.get('reason', 'Suspended by admin')
        pharmacy.save()

        # Log action
        AdminActivityLog.objects.create(
            admin=request.user,
            action='PHARMACY_SUSPENDED',
            target_model='Pharmacy',
            target_id=pharmacy.id,
            description=f"Suspended {pharmacy.name}",
            ip_address=get_client_ip(request)
        )

        return Response({
            'message': 'Pharmacy suspended',
            'pharmacy': PharmacySerializer(pharmacy).data
        })

# ============================================
# CUSTOMER VIEWSETS  (customers_d.Customer)
# ============================================
class CustomerViewSet(viewsets.ModelViewSet):
    """Customer CRUD + Admin Actions"""
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = Customer.objects.select_related('user').all()

        # Filters ("blocked"/"active" are derived from CustomUser.is_active)
        status_filter = self.request.query_params.get('status')
        if status_filter == 'blocked':
            queryset = queryset.filter(user__is_active=False)
        elif status_filter == 'active':
            queryset = queryset.filter(user__is_active=True)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__username__icontains=search)
            )

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return CustomerListSerializer
        return CustomerSerializer

    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        """Block customer (real model has no is_blocked field; this maps
        onto CustomUser.is_active, the same flag UserLoginSerializer
        already checks to refuse blocked accounts at login)."""
        customer = self.get_object()
        customer.user.is_active = False
        customer.user.save()

        # Log
        AdminActivityLog.objects.create(
            admin=request.user,
            action='CUSTOMER_BLOCKED',
            target_model='Customer',
            target_id=customer.id,
            description=f"Blocked {customer.user.email}",
            ip_address=get_client_ip(request)
        )

        return Response({'message': 'Customer blocked'})

    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        """Unblock customer"""
        customer = self.get_object()
        customer.user.is_active = True
        customer.user.save()

        AdminActivityLog.objects.create(
            admin=request.user,
            action='CUSTOMER_UNBLOCKED',
            target_model='Customer',
            target_id=customer.id,
            description=f"Unblocked {customer.user.email}",
            ip_address=get_client_ip(request)
        )

        return Response({'message': 'Customer unblocked'})

# ============================================
# MEDICINE VIEWSETS  (dashboards.Medicine)
#
# MedicineCategoryViewSet is a plain ViewSet, not a ModelViewSet: there is
# no live MedicineCategory table to back it. "Categories" are just the
# distinct `category` string values already on dashboards.Medicine, so
# this only supports list/retrieve (read-only) — nothing to create/
# update/delete against.
# ============================================
class MedicineCategoryViewSet(viewsets.ViewSet):
    """Read-only virtual medicine categories, derived from Medicine.category"""
    permission_classes = [permissions.AllowAny]

    def _category_qs(self):
        return (
            Medicine.objects.exclude(category__isnull=True)
            .exclude(category__exact='')
            .values('category')
            .annotate(medicine_count=Count('id'))
            .order_by('category')
        )

    def list(self, request):
        rows = [
            {'name': row['category'], 'medicine_count': row['medicine_count']}
            for row in self._category_qs()
        ]
        serializer = MedicineCategorySerializer(rows, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        row = self._category_qs().filter(category=pk).first()
        if not row:
            return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = MedicineCategorySerializer(
            {'name': row['category'], 'medicine_count': row['medicine_count']}
        )
        return Response(serializer.data)

class MedicineViewSet(viewsets.ModelViewSet):
    """Medicine CRUD"""
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.action == 'list':
            return MedicineListSerializer
        return MedicineSerializer

    def get_queryset(self):
        queryset = Medicine.objects.all()

        # category is a free-text field on the live model (not an FK id)
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__iexact=category)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(brand__icontains=search)
            )

        return queryset

    def perform_update(self, serializer):
        """Ban/unban is now a direct field update on the live Medicine row
        itself (no mirroring needed — dashboards.Medicine IS the row the
        pharmacy dashboard and storefront read)."""
        instance = serializer.instance
        prev_is_banned = getattr(instance, 'is_banned', False)

        updated = serializer.save()
        new_is_banned = getattr(updated, 'is_banned', False)

        if prev_is_banned != new_is_banned:
            AdminActivityLog.objects.create(
                admin=self.request.user,
                action='MEDICINE_BANNED' if new_is_banned else 'MEDICINE_UNBANNED',
                target_model='Medicine',
                target_id=updated.id,
                description=f"{'Banned' if new_is_banned else 'Unbanned'} {updated.name}",
                ip_address=get_client_ip(self.request),
            )

# ============================================
# ORDER VIEWSETS  (orders.Order)
# ============================================
class OrderViewSet(viewsets.ModelViewSet):
    """Order Management"""
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsCustomer()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'list':
            return OrderListSerializer
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_admin_user:
            # Admin sees all
            queryset = Order.objects.all()
        elif user.is_pharmacist_user:
            # Pharmacist sees their pharmacy's orders (dashboards.Pharmacy
            # related_name is 'pharmacy', not 'pharmacy_profile')
            pharmacy = getattr(user, 'pharmacy', None)
            queryset = Order.objects.filter(pharmacy=pharmacy) if pharmacy else Order.objects.none()
        else:
            # Customer sees their own orders. orders.Order links straight
            # to CustomUser via `user` — there's no Customer FK to go
            # through.
            queryset = Order.objects.filter(user=user)

        # Filters (real status values are Title Case, e.g. 'Pending')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)

        return queryset.order_by('-created_at')

    def create(self, request):
        """Create new order"""
        serializer = OrderCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            order = serializer.save()
            return Response(
                OrderSerializer(order).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update order status"""
        order = self.get_object()
        new_status = request.data.get('status', '')

        # Real status values are Title Case ('Pending', 'Approved', ...);
        # accept case-insensitively but store using the canonical form.
        match = next(
            (s for s in ORDER_STATUS_VALUES if s.lower() == str(new_status).lower()),
            None
        )
        if match:
            order.status = match
            order.save()
            return Response({'message': 'Status updated', 'status': match})

        return Response(
            {'error': f'Invalid status. Must be one of: {", ".join(ORDER_STATUS_VALUES)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

# ============================================
# PRESCRIPTION VIEWSETS  (customers_d.Prescription)
# ============================================
class PrescriptionViewSet(viewsets.ModelViewSet):
    """Prescription Management"""
    queryset = Prescription.objects.all()
    serializer_class = PrescriptionSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_admin_user:
            queryset = Prescription.objects.all()
        elif user.is_pharmacist_user:
            # Prescription.pharmacy is a direct FK to the pharmacy's CustomUser
            queryset = Prescription.objects.filter(pharmacy=user)
        else:
            # Prescription.customer is a direct FK to the customer's CustomUser
            queryset = Prescription.objects.filter(customer=user)

        # Real status values are lowercase: pending/approved/rejected
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status__iexact=status_filter)

        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        """Verify (approve) prescription"""
        prescription = self.get_object()

        prescription.status = 'approved'
        prescription.save()

        # Log
        AdminActivityLog.objects.create(
            admin=request.user,
            action='PRESCRIPTION_VERIFIED',
            target_model='Prescription',
            target_id=prescription.id,
            description=f"Verified prescription PRX-{prescription.id}",
            ip_address=get_client_ip(request)
        )

        return Response({'message': 'Prescription verified'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def flag(self, request, pk=None):
        """
        Flag prescription. The live model has no separate FLAGGED status
        (only pending/approved/rejected), so flagging is stored as a
        rejection with a reason — same convention already used by
        dashboards/views.py::reject_prescription.
        """
        prescription = self.get_object()
        reason = request.data.get('reason', 'Suspicious document')

        prescription.status = 'rejected'
        prescription.rejection_reason = reason
        prescription.save()

        AdminActivityLog.objects.create(
            admin=request.user,
            action='PRESCRIPTION_REJECTED',
            target_model='Prescription',
            target_id=prescription.id,
            description=f"Flagged prescription PRX-{prescription.id}: {reason}",
            ip_address=get_client_ip(request)
        )

        return Response({'message': 'Prescription flagged'})

# ============================================
# NOTIFICATION VIEWSETS  (admin_panel.Notification)
# ============================================
class NotificationViewSet(viewsets.ModelViewSet):
    """Notifications"""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_admin_user:
            return Notification.objects.all()

        # User's notifications
        return Notification.objects.filter(
            Q(recipient_type='ALL')
        ).order_by('-created_at')

    def create(self, request):
        """Send notification (admin only)"""
        if not request.user.is_admin_user:
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = NotificationCreateSerializer(data=request.data)
        if serializer.is_valid():
            notification = serializer.save()
            # Fan out to the real CustomerNotification / PharmacyNotification
            # tables (+ websocket push) so the recipients actually see it —
            # saving to admin_panel.Notification alone never reached them.
            from .notification_utils import fanout_notification
            fanout_notification(notification)
            return Response(
                NotificationSerializer(notification).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ============================================
# ADMIN LOG VIEWSETS
# ============================================
class AdminActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin Activity Logs (Read Only)"""
    queryset = AdminActivityLog.objects.all()
    serializer_class = AdminActivityLogSerializer
    permission_classes = [IsAdminUser]

class LoginLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Login Logs (Read Only)"""
    queryset = LoginLog.objects.all()
    serializer_class = LoginLogSerializer
    permission_classes = [IsAdminUser]

# ============================================
# SYSTEM SETTINGS
# ============================================
class SystemSettingsViewSet(viewsets.ModelViewSet):
    """System Settings"""
    queryset = SystemSettings.objects.all()
    serializer_class = SystemSettingsSerializer
    permission_classes = [IsAdminUser]

    def perform_update(self, serializer):
        serializer.save()


# ============================================
# USER MANAGEMENT (ADMIN ONLY)
# ============================================
class UserViewSet(viewsets.ModelViewSet):
    """Create/read/update/delete users (admin only)"""
    queryset = CustomUser.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = CustomUser.objects.all()
        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(email__icontains=search) |
                Q(username__icontains=search)
            )
        return qs.order_by('-date_joined')