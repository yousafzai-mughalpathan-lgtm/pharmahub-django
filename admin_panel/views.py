"""
PHARMAHUB - Admin Panel Views
Views for Custom Admin UI Templates
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from authentication.decorators import role_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.conf import settings
from datetime import timedelta
import json
from admin_panel.models import Notification, AdminActivityLog

import logging
import csv
import re

from .models import (
    Notification, SystemSettings, SecurityLog,
    AdminActivityLog, LoginLog
)

# Real pharmacy + medicine models live in dashboards app.
# IMPORTANT: Use dashboards.Pharmacy / dashboards.Medicine, because the old
# admin_panel.Pharmacy / admin_panel.Medicine duplicates are disconnected.
from dashboards.models import Pharmacy, Medicine, PharmacyNotification
from dashboards.utils import geocode_address

# Real orders app models
from orders.models import Order, OrderItem, Payment

# Real customer/prescription models
from customers_d.models import Customer, Prescription


logger = logging.getLogger(__name__)


# ===== HELPER FUNCTIONS =====
def is_admin(user):
    """Check if user is admin"""
    return user.is_staff or user.is_superuser or (
        hasattr(user, 'is_admin_user') and user.is_admin_user
    )


def get_client_ip(request):
    """Get client IP address (handles proxy headers)."""
    # Prefer X-Real-IP if present
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip.strip()

    # Fall back to X-Forwarded-For
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # May contain a list of IPs: client, proxy1, proxy2...
        return x_forwarded_for.split(',')[0].strip()

    return request.META.get('REMOTE_ADDR', '0.0.0.0')


# ===== AUTHENTICATION VIEWS =====
def admin_login(request):
    """Admin login page"""
    if request.user.is_authenticated:
        return redirect('admin_panel:admin_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None and is_admin(user):
            login(request, user)
            
            # Log successful login
            LoginLog.objects.create(
                user=user,
                email_attempted=user.email,
                status='SUCCESS',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            
            messages.success(request, 'Successfully logged in!')
            return redirect('admin_panel:admin_dashboard')
        else:
            # Log failed login (ensure email_attempted is never null)
            LoginLog.objects.create(
                email_attempted=username or '',
                status='FAILED',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                failure_reason='Invalid credentials or not admin user'
            )
            
            messages.error(request, 'Invalid credentials or insufficient permissions')
    
    return render(request, 'admin/login.html')


@login_required
def admin_logout(request):
    """Admin logout"""
    logout(request)
    messages.success(request, 'Successfully logged out')
    return redirect('admin_panel:admin_login')


# ===== DASHBOARD =====
@role_required('admin', 'super_admin')
def admin_dashboard(request):
    """Admin dashboard with statistics"""
    
    # Get statistics
    total_pharmacies = Pharmacy.objects.count()
    verified_pharmacies = Pharmacy.objects.filter(verification_status='approved').count()
    pending_pharmacies = Pharmacy.objects.filter(verification_status='pending').count()

    
    # customers_d.Customer has no is_blocked field; "blocked" is
    # CustomUser.is_active == False (same flag the login flow checks).
    total_customers = Customer.objects.count()
    active_customers = Customer.objects.filter(user__is_active=True).count()

    # orders.Order.status is free text; real values are Title Case.
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='Pending').count()
    
    # Revenue calculation (orders.Payment.status choices are lowercase)
    total_revenue = Payment.objects.filter(status='success').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Monthly sales for chart
    current_year = timezone.now().year
    monthly_sales = []
    for month in range(1, 13):
        month_total = Payment.objects.filter(
            status='success',
            created_at__year=current_year,
            created_at__month=month
        ).aggregate(total=Sum('amount'))['total'] or 0
        monthly_sales.append(float(month_total))
    
    # Recent activities. orders.Order links to the customer via `user`
    # directly — there is no `customer` relation on the live model.
    recent_orders = Order.objects.select_related(
        'user', 'pharmacy'
    ).order_by('-created_at')[:5]

    # dashboards.Pharmacy model me created_at nahi hai; submitted_at/verified_at use karo
    recent_pharmacies = Pharmacy.objects.order_by('-submitted_at')[:5]


    
    # System alerts
    alerts = []
    if pending_pharmacies > 0:
        alerts.append({
            'type': 'warning',
            'message': f'{pending_pharmacies} pharmacies pending verification'
        })

    # Quick-search: the header search box (present on every admin page)
    # submits ?q= to whatever page is currently open. Every other admin
    # page reads it already; the dashboard used to ignore it entirely.
    search_query = request.GET.get('q', '').strip()
    search_results = None
    if search_query:
        search_results = {
            'query': search_query,
            'pharmacies': Pharmacy.objects.filter(
                Q(name__icontains=search_query) |
                Q(owner_name__icontains=search_query) |
                Q(license_number__icontains=search_query)
            )[:5],
            'customers': Customer.objects.select_related('user').filter(
                Q(user__username__icontains=search_query) |
                Q(user__email__icontains=search_query) |
                Q(user__first_name__icontains=search_query) |
                Q(user__last_name__icontains=search_query)
            )[:5],
            'orders': Order.objects.select_related('user', 'pharmacy').filter(
                Q(id__icontains=search_query) |
                Q(user__username__icontains=search_query) |
                Q(user__email__icontains=search_query)
            )[:5],
        }

    context = {
        'total_pharmacies': total_pharmacies,
        'verified_pharmacies': verified_pharmacies,
        'pending_pharmacies': pending_pharmacies,
        'total_customers': total_customers,
        'active_customers': active_customers,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'total_revenue': total_revenue,
        'monthly_sales': monthly_sales,
        'recent_orders': recent_orders,
        'recent_pharmacies': recent_pharmacies,
        'alerts': alerts,
        'search_query': search_query,
        'search_results': search_results,
    }
    
    return render(request, 'admin/admin_dashboard.html', context)


# ===== PHARMACY VERIFICATION =====
@role_required('admin', 'super_admin')
def pharmacy_verification(request):
    # Pending queue based on verification_status
    pharmacies = Pharmacy.objects.filter(
        verification_status='pending'
    ).order_by('-submitted_at')

    
    context = {
        'pharmacies': pharmacies,
        'pending_count': pharmacies.count(),
        'approved_count': Pharmacy.objects.filter(verification_status='approved').count(),
    }

    # Tasalli ke liye terminal mein check karein
    print(f"DEBUG: Found {pharmacies.count()} pharmacies for template")
    
    return render(request, 'admin/pharmacy_verification.html', context)


@role_required('admin', 'super_admin')
def approve_pharmacy(request, pk):
    # 1. Pharmacy ko database se nikalna
    pharmacy = get_object_or_404(Pharmacy, pk=pk)
    
    # 2. Database Update
    pharmacy.is_verified = True
    pharmacy.verification_status = 'approved'
    pharmacy.verified_at = timezone.now()
    pharmacy.save()


    
    # 3. Notification Create Karein (recipient FK can be NULL)
    # dashboards.Pharmacy.user is expected to exist, but to avoid IntegrityError we guard.
    if pharmacy.user_id:
        Notification.objects.create(
            recipient=pharmacy.user,
            title="Pharmacy Approved! 🎉",
            content=f"Your pharmacy '{pharmacy.name}' has been verified and is now active.",
            recipient_type='SPECIFIC',
            notification_type='ANNOUNCEMENT',
            is_urgent=True
        )
        # Also create a PharmacyNotification so the pharmacy dashboard sees it
        PharmacyNotification.objects.create(
            user=pharmacy.user,
            message=f"Pharmacy Approved! Your pharmacy '{pharmacy.name}' has been verified and is now active.",
        )
    else:
        Notification.objects.create(
            recipient=None,
            title="Pharmacy Approved! 🎉",
            content=f"Your pharmacy '{pharmacy.name}' has been verified and is now active.",
            recipient_type='PHARMACIES',
            notification_type='ANNOUNCEMENT',
            is_urgent=True
        )
    
    # 4. Email bhejne ka process
    subject = 'PharmaHub - Pharmacy Approved!'
    message = (
        f"Dear {pharmacy.owner_name},\n\n"
        f"Good news! Your pharmacy '{pharmacy.name}' has been officially verified.\n"
        "Regards,\nPharmaHub Admin Team"
    )
    recipient_list = [pharmacy.email]
    
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
    except Exception as e:
        print(f"Email error: {e}")

    # 5. Activity Log
    AdminActivityLog.objects.create(
        admin=request.user,
        action='PHARMACY_APPROVED',
        target_model='Pharmacy',
        target_id=pharmacy.id,
        description=f'Approved pharmacy: {pharmacy.name}',
        ip_address=get_client_ip(request)
    )

    # 6. Success Message aur Redirect
    messages.success(request, f"Pharmacy '{pharmacy.name}' approved successfully!")
    return redirect('admin_panel:pharmacy_verification')


@role_required('admin', 'super_admin')
def reject_pharmacy(request, pk):
    pharmacy = get_object_or_404(Pharmacy, pk=pk)
    
    # Action perform karein
    pharmacy.is_verified = False
    pharmacy.verification_status = 'rejected'
    pharmacy.rejection_reason = request.POST.get('reason', '')
    pharmacy.save()

    # 1. Dashboard Notification for Rejection (recipient FK can be NULL)
    if pharmacy.user_id:
        Notification.objects.create(
            recipient=pharmacy.user,
            title="Application Rejected ❌",
            content=f"We regret to inform you that your pharmacy '{pharmacy.name}' application was not approved. Please contact support for details.",
            recipient_type='SPECIFIC',
            notification_type='ANNOUNCEMENT',
            is_urgent=True
        )
        PharmacyNotification.objects.create(
            user=pharmacy.user,
            message=f"Application Rejected. Your pharmacy '{pharmacy.name}' application was not approved.",
        )
    else:
        Notification.objects.create(
            recipient=None,
            title="Application Rejected ❌",
            content=f"We regret to inform you that your pharmacy '{pharmacy.name}' application was not approved. Please contact support for details.",
            recipient_type='PHARMACIES',
            notification_type='ANNOUNCEMENT',
            is_urgent=True
        )

   # 2. Email bhejna
    subject = 'PharmaHub - Pharmacy Application Rejected'
    message = (
        f"Dear {pharmacy.owner_name},\n\n"
        f"We regret to inform you that your pharmacy '{pharmacy.name}' application was not approved.\n"
        "Please contact support for details.\n"
        "Regards,\nPharmaHub Admin Team"
    )
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [pharmacy.email])
    except Exception as e:
        print(f"Email error: {e}")

    # 3. Activity Log (Zaroori hai record ke liye)
    AdminActivityLog.objects.create(
        admin=request.user,
        action='PHARMACY_REJECTED',
        target_model='Pharmacy',
        target_id=pharmacy.id,
        description=f'Rejected pharmacy: {pharmacy.name}',
        ip_address=get_client_ip(request)
    )
    
    messages.warning(request, f"Pharmacy '{pharmacy.name}' has been rejected.")
    return redirect('admin_panel:pharmacy_verification')


@role_required('admin', 'super_admin')
def pharmacist_verification(request):
    """Pharmacist license approval page"""
    from authentication.models import CustomUser
    # Avoid crash if field doesn't exist in some deployments.
    if hasattr(CustomUser, 'is_verified_pharmacist'):
        pharmacists = CustomUser.objects.filter(role='pharmacist', is_verified_pharmacist=False)
    else:
        pharmacists = CustomUser.objects.filter(role='pharmacist')

    context = {
        'pharmacists': pharmacists,
        'pending_count': pharmacists.count(),
    }
    return render(request, 'admin/pharmacist_verification.html', context)


@role_required('admin', 'super_admin')
def approve_pharmacist(request, pk):
    from authentication.models import CustomUser
    pharmacist = get_object_or_404(CustomUser, pk=pk, role='pharmacist')
    pharmacist.is_verified_pharmacist = True
    pharmacist.is_active = True
    pharmacist.save()
    AdminActivityLog.objects.create(
        admin=request.user,
        action='PHARMACIST_APPROVED',
        target_model='CustomUser',
        target_id=pharmacist.id,
        description=f'Approved pharmacist: {pharmacist.email}',
        ip_address=get_client_ip(request)
    )
    try:
        send_mail(
            subject='Your pharmacist account has been approved',
            message=(
                f"Dear {pharmacist.username or pharmacist.email},\n\n"
                "Your pharmacist profile on PharmaHub is now approved. You may log in and "
                "access pharmacist features.\n\n"
                "Regards,\nPharmaHub Team"
            ),
            from_email=None,
            recipient_list=[pharmacist.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception('Failed to send email to pharmacist %s', pharmacist.email)
    messages.success(request, f'Pharmacist {pharmacist.email} approved')
    return redirect('admin_panel:pharmacist_verification')


@role_required('admin', 'super_admin')
def reject_pharmacist(request, pk):
    from authentication.models import CustomUser
    pharmacist = get_object_or_404(CustomUser, pk=pk, role='pharmacist')
    pharmacist.is_active = False
    pharmacist.save()
    AdminActivityLog.objects.create(
        admin=request.user,
        action='PHARMACIST_REJECTED',
        target_model='CustomUser',
        target_id=pharmacist.id,
        description=f'Rejected pharmacist: {pharmacist.email}',
        ip_address=get_client_ip(request)
    )
    try:
        send_mail(
            subject='Your pharmacist account has been rejected',
            message=(
                "Dear user,\n\nYour pharmacist registration has been rejected. "
                "Please verify your documents and resubmit or contact support.\n\n"
                "Regards,\nPharmaHub Team"
            ),
            from_email=None,
            recipient_list=[pharmacist.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception('Failed to send rejection email to pharmacist %s', pharmacist.email)
    messages.warning(request, f'Pharmacist {pharmacist.email} rejected')
    return redirect('admin_panel:pharmacist_verification')


# ===== USER MANAGEMENT =====
@role_required('admin', 'super_admin')
def user_management(request):
    """Enhanced user management page with statistics, filtering, and pagination"""
    from authentication.models import CustomUser
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    # Base queryset
    users = CustomUser.objects.all().order_by('-date_joined')
    
    # Search functionality
    search = request.GET.get('q', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    
    # Apply filters
    if search:
        users = users.filter(
            Q(email__icontains=search) | Q(username__icontains=search)
        )
    
    if role_filter:
        users = users.filter(role=role_filter)
    
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    # Statistics
    total_users = CustomUser.objects.count()
    active_users = CustomUser.objects.filter(is_active=True).count()
    inactive_users = CustomUser.objects.filter(is_active=False).count()
    
    # Count by role
    role_stats = {
        'admin': CustomUser.objects.filter(role='admin').count(),
        'super_admin': CustomUser.objects.filter(role='super_admin').count(),
        'customer': CustomUser.objects.filter(role='customer').count(),
        'pharmacy': CustomUser.objects.filter(role='pharmacy').count(),
        'pharmacist': CustomUser.objects.filter(role='pharmacist').count(),
    }
    
    # Pagination
    paginator = Paginator(users, 15)  # 15 users per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'users': page_obj.object_list,
        'search': search,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'role_stats': role_stats,
        'role_choices': CustomUser._meta.get_field('role').choices,
    }
    return render(request, 'admin/user_management.html', context)


@role_required('admin', 'super_admin')
def user_detail(request, pk):
    """View user details and activity"""
    from authentication.models import CustomUser
    user = get_object_or_404(CustomUser, pk=pk)
    
    # Get user activity logs
    activity_logs = AdminActivityLog.objects.filter(target_id=pk, target_model='CustomUser').order_by('-created_at')[:10]
    
    # Get related data based on role
    related_data = {}
    if user.role == 'pharmacy':
        related_data['pharmacy'] = Pharmacy.objects.filter(user=user).first()
    elif user.role == 'customer':
        related_data['customer'] = Customer.objects.filter(user=user).first()
        related_data['orders'] = Order.objects.filter(user=user).count()
        related_data['lifetime_spent'] = Order.objects.filter(
            user=user, status='Delivered'
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    # Get login history
    login_history = LoginLog.objects.filter(user=user).order_by('-created_at')[:10]
    
    context = {
        'user': user,
        'activity_logs': activity_logs,
        'login_history': login_history,
        'related_data': related_data,
    }
    return render(request, 'admin/user_detail.html', context)


@role_required('admin', 'super_admin')
def edit_user_role(request, pk):
    """Edit user role"""
    from authentication.models import CustomUser
    user = get_object_or_404(CustomUser, pk=pk)
    
    if request.method == 'POST':
        new_role = request.POST.get('role')
        old_role = user.role
        
        if new_role in dict(CustomUser._meta.get_field('role').choices):
            user.role = new_role
            user.save()
            
            AdminActivityLog.objects.create(
                admin=request.user,
                action='USER_ROLE_CHANGED',
                target_model='CustomUser',
                target_id=user.id,
                description=f'Changed role from {old_role} to {new_role} for user: {user.email}',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'User role updated from {old_role} to {new_role}')
            return redirect('admin_panel:user_detail', pk=pk)
    
    context = {
        'user': user,
        'role_choices': CustomUser._meta.get_field('role').choices,
    }
    return render(request, 'admin/edit_user_role.html', context)


@role_required('admin', 'super_admin')
def toggle_user_active(request, pk):
    """Toggle user active status"""
    from authentication.models import CustomUser
    user = get_object_or_404(CustomUser, pk=pk)
    
    # Don't allow disabling super_admin accounts (including self)
    if user.role == 'super_admin':
        messages.error(request, 'Cannot disable super admin accounts')
        return redirect('admin_panel:user_management')

    user.is_active = not user.is_active

    user.save()
    action = 'ENABLED' if user.is_active else 'DISABLED'
    
    AdminActivityLog.objects.create(
        admin=request.user,
        action=f'USER_{action}',
        target_model='CustomUser',
        target_id=user.id,
        description=f'{action} user: {user.email}',
        ip_address=get_client_ip(request)
    )
    
    messages.success(request, f'User {user.email} has been {action.lower()}')
    return redirect('admin_panel:user_detail', pk=pk)


@role_required('admin', 'super_admin')
def delete_user(request, pk):
    """Delete a user account"""
    from authentication.models import CustomUser
    user = get_object_or_404(CustomUser, pk=pk)
    
    # Prevent deletion of super_admin accounts
    if user.role == 'super_admin':
        messages.error(request, 'Cannot delete super admin accounts')
        return redirect('admin_panel:user_management')
    
    if request.method == 'POST':
        email = user.email
        user_id = user.id
        
        AdminActivityLog.objects.create(
            admin=request.user,
            action='USER_DELETED',
            target_model='CustomUser',
            target_id=user_id,
            description=f'Deleted user account: {email}',
            ip_address=get_client_ip(request)
        )
        
        user.delete()
        messages.success(request, f'User {email} has been successfully deleted')
        return redirect('admin_panel:user_management')
    
    context = {
        'user': user,
    }
    return render(request, 'admin/delete_user_confirm.html', context)


@role_required('admin', 'super_admin')
def export_users_csv(request):
    """Export users to CSV"""
    from authentication.models import CustomUser
    from django.db.models import Q

    # Apply same filters as user_management view
    users = CustomUser.objects.all()
    search = request.GET.get('q', '')
    role_filter = request.GET.get('role', '')

    if search:
        users = users.filter(
            Q(email__icontains=search) | Q(username__icontains=search)
        )
    if role_filter:
        users = users.filter(role=role_filter)

    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="users_export.csv"'},
    )

    writer = csv.writer(response)
    writer.writerow(['Email', 'Username', 'Role', 'Active', 'Verified Pharmacist', 'Date Joined'])

    for user in users:
        is_verified_pharmacist = getattr(user, 'is_verified_pharmacist', False)
        writer.writerow([
            user.email,
            user.username,
            user.get_role_display(),
            'Yes' if user.is_active else 'No',
            'Yes' if is_verified_pharmacist else 'No',
            user.date_joined.strftime('%Y-%m-%d %H:%M'),
        ])

    return response


# ===== PHARMACY MANAGEMENT =====
@role_required('admin', 'super_admin')
def pharmacy_management(request):
    """Pharmacy management page"""
    pharmacies = Pharmacy.objects.all().order_by('-submitted_at')

    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        pharmacies = pharmacies.filter(
            Q(name__icontains=search_query) |
            Q(owner_name__icontains=search_query) |
            Q(license_number__icontains=search_query)
        )
    
    # Filter
    status_filter = request.GET.get('status', '')
    if status_filter == 'verified':
        pharmacies = pharmacies.filter(is_verified=True)
    elif status_filter == 'unverified':
        pharmacies = pharmacies.filter(is_verified=False, verification_status__in=['pending'])
    elif status_filter == 'suspended':
        # dashboards.Pharmacy model me is_suspended field available nahi hai.
        # Suspension ko same flow me is_verified=False + verification_status='rejected' se map kiya ja raha hai.
        pharmacies = pharmacies.filter(is_verified=False, verification_status='rejected')

    suspended_count = Pharmacy.objects.filter(is_verified=False, verification_status='rejected').count()

    context = {
        'pharmacies': pharmacies,
        'total_pharmacies': Pharmacy.objects.count(),
        'verified_count': Pharmacy.objects.filter(is_verified=True).count(),
        'suspended_count': suspended_count,
        # dashboards.Pharmacy has no rating field — no live rating data exists yet.
        'avg_rating': 0,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    
    return render(request, 'admin/pharmacy_management.html', context)


@role_required('admin', 'super_admin')
def suspend_pharmacy(request, pk):
    """Suspend pharmacy"""
    pharmacy = get_object_or_404(Pharmacy, pk=pk)
    # dashboards.Pharmacy has no is_suspended field. "Suspended" is
    # represented as is_verified=False + verification_status='rejected' —
    # the same combination pharmacy_management's suspended-filter checks.
    pharmacy.is_verified = False
    pharmacy.verification_status = 'rejected'
    pharmacy.save()

    AdminActivityLog.objects.create(
        admin=request.user,
        action='PHARMACY_SUSPENDED',
        target_model='Pharmacy',
        target_id=pharmacy.id,
        description=f'Suspended pharmacy: {pharmacy.name}',
        ip_address=get_client_ip(request)
    )
    
    messages.warning(request, f'{pharmacy.name} has been suspended')
    return redirect('admin_panel:pharmacy_management')


@role_required('admin', 'super_admin')
def activate_pharmacy(request, pk):
    """Activate pharmacy"""
    pharmacy = get_object_or_404(Pharmacy, pk=pk)
    pharmacy.is_verified = True
    pharmacy.verification_status = 'approved'
    pharmacy.save()

    AdminActivityLog.objects.create(
        admin=request.user,
        action='PHARMACY_REACTIVATED',
        target_model='Pharmacy',
        target_id=pharmacy.id,
        description=f'Reactivated pharmacy: {pharmacy.name}',
        ip_address=get_client_ip(request)
    )
    
    messages.success(request, f'{pharmacy.name} has been activated')
    return redirect('admin_panel:pharmacy_management')


@role_required('admin', 'super_admin')
def update_pharmacy_location(request, pk):
    """Set/update a pharmacy's latitude & longitude from the custom admin panel"""
    pharmacy = get_object_or_404(Pharmacy, pk=pk)

    if request.method == 'POST':
        if request.POST.get('auto') == '1':
            lat, lng = geocode_address(pharmacy.address, pharmacy.city)
            if lat is not None and lng is not None:
                pharmacy.latitude = lat
                pharmacy.longitude = lng
                pharmacy.save()
                messages.success(request, f'Auto-located {pharmacy.name} from its address')
            else:
                messages.error(request, f'Could not auto-locate {pharmacy.name} — enter coordinates manually')
            return redirect('admin_panel:pharmacy_management')

        lat = request.POST.get('latitude', '').strip()
        lng = request.POST.get('longitude', '').strip()

        try:
            pharmacy.latitude = float(lat) if lat else None
            pharmacy.longitude = float(lng) if lng else None
            pharmacy.save()

            AdminActivityLog.objects.create(
                admin=request.user,
                action='PHARMACY_LOCATION_UPDATED',
                target_model='Pharmacy',
                target_id=pharmacy.id,
                description=f'Updated location for pharmacy: {pharmacy.name} ({lat}, {lng})',
                ip_address=get_client_ip(request)
            )
            messages.success(request, f'Location updated for {pharmacy.name}')
        except ValueError:
            messages.error(request, 'Latitude/Longitude must be valid numbers')

    return redirect('admin_panel:pharmacy_management')


# ===== CUSTOMER MANAGEMENT =====
@role_required('admin', 'super_admin')
def customer_management(request):
    """Customer management page (this page's live table is actually loaded
    client-side from /api/customers/ — see CustomerViewSet — but this
    context is still populated for consistency / non-JS fallback)."""
    customers = Customer.objects.select_related('user').all()

    # customers_d.Customer has no is_blocked field of its own — "blocked"
    # is CustomUser.is_active == False, the same flag the login flow checks.
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        customers = customers.filter(user__is_active=True)
    elif status_filter == 'blocked':
        customers = customers.filter(user__is_active=False)

    context = {
        'customers': customers,
        'total_customers': Customer.objects.count(),
        'active_count': Customer.objects.filter(user__is_active=True).count(),
        'blocked_count': Customer.objects.filter(user__is_active=False).count(),
    }
    
    return render(request, 'admin/customer_management.html', context)


@role_required('admin', 'super_admin')
def block_customer(request, pk):
    """Block customer. customers_d.Customer has no is_blocked field —
    blocking means deactivating the underlying auth user, the same flag
    the login flow already checks."""
    customer = get_object_or_404(Customer, pk=pk)
    customer.user.is_active = False
    customer.user.save(update_fields=['is_active'])

    AdminActivityLog.objects.create(
        admin=request.user,
        action='CUSTOMER_BLOCKED',
        target_model='Customer',
        target_id=customer.id,
        description=f'Blocked customer: {customer.user.username}',
        ip_address=get_client_ip(request)
    )
    
    messages.warning(request, f'Customer {customer.user.username} has been blocked')
    return redirect('admin_panel:customer_management')


@role_required('admin', 'super_admin')
def unblock_customer(request, pk):
    """Unblock customer"""
    customer = get_object_or_404(Customer, pk=pk)
    customer.user.is_active = True
    customer.user.save(update_fields=['is_active'])

    AdminActivityLog.objects.create(
        admin=request.user,
        action='CUSTOMER_UNBLOCKED',
        target_model='Customer',
        target_id=customer.id,
        description=f'Unblocked customer: {customer.user.username}',
        ip_address=get_client_ip(request)
    )
    
    messages.success(request, f'Customer {customer.user.username} has been unblocked')
    return redirect('admin_panel:customer_management')


# ===== MEDICINE CONTROL =====
@role_required('admin', 'super_admin')
def medicine_control(request):
    """Medicine control page (the live table/category list is actually
    loaded client-side from /api/medicines/ and /api/medicine-categories/;
    this context is kept for consistency / non-JS fallback)."""
    # dashboards.Medicine.category is a plain string field — there is no
    # live MedicineCategory table, so "categories" are just the distinct
    # values already on Medicine.
    categories = (
        Medicine.objects.exclude(category__isnull=True)
        .exclude(category__exact='')
        .values('category')
        .annotate(medicine_count=Count('id'))
        .order_by('category')
    )
    banned_medicines = Medicine.objects.filter(is_banned=True)

    context = {
        'categories': categories,
        'total_medicines': Medicine.objects.count(),
        'total_categories': categories.count(),
        'banned_count': banned_medicines.count(),
        'banned_medicines': banned_medicines,
    }
    
    return render(request, 'admin/medicine_control.html', context)


@role_required('admin', 'super_admin')
def add_medicine_category(request):
    """
    'Add category' has no live table to persist to — dashboards.Medicine
    stores category as a plain string, not a FK to a category table, so a
    category only exists once a medicine actually uses it.
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            messages.info(
                request,
                f'"{name}" will appear automatically once a medicine is '
                'saved with that category — there is no separate category '
                'list to add to.'
            )
    
    return redirect('admin_panel:medicine_control')


@role_required('admin', 'super_admin')
def ban_medicine(request, pk):
    """Ban medicine"""
    medicine = get_object_or_404(Medicine, pk=pk)
    ban_reason = request.POST.get('reason', 'Banned by admin')

    # medicine is already the live dashboards.Medicine row — the pharmacy
    # dashboard and storefront read this exact table, so there's nothing
    # left to mirror into.
    medicine.is_banned = True
    medicine.ban_reason = ban_reason
    medicine.save()

    AdminActivityLog.objects.create(
        admin=request.user,
        action='MEDICINE_BANNED',
        target_model='Medicine',
        target_id=medicine.id,
        description=f'Banned medicine: {medicine.name}',
        ip_address=get_client_ip(request)
    )

    messages.warning(request, f'{medicine.name} has been banned')
    return redirect('admin_panel:medicine_control')


@role_required('admin', 'super_admin')
def unban_medicine(request, pk):
    """Unban medicine"""
    medicine = get_object_or_404(Medicine, pk=pk)
    # If UI sends reason, keep it; otherwise set default.
    ban_reason = request.POST.get('reason', '').strip() or ''

    # medicine is already the live dashboards.Medicine row — nothing to
    # mirror, this IS the row the storefront reads.
    medicine.is_banned = False
    medicine.ban_reason = ban_reason
    medicine.save()

    AdminActivityLog.objects.create(
        admin=request.user,
        action='MEDICINE_UNBANNED',
        target_model='Medicine',
        target_id=medicine.id,
        description=f'Unbanned medicine: {medicine.name}',
        ip_address=get_client_ip(request)
    )

    messages.success(request, f'{medicine.name} has been unbanned')
    return redirect('admin_panel:medicine_control')


# ===== ORDERS MONITORING =====
@role_required('admin', 'super_admin')
def orders_monitoring(request):
    """
    Orders monitoring page. NOTE: the visible table in this template is
    actually loaded client-side from `${API_BASE_URL}/admin/orders/`
    (see orders_monitoring.html) — that endpoint doesn't exist in urls.py
    (only /api/orders/ does, via OrderViewSet). That's a separate,
    pre-existing frontend-wiring gap, not a duplicate-model issue, so it's
    flagged here rather than silently patched. This Django context is
    fixed for correctness/consistency regardless.
    """
    # orders.Order links to the customer via `user` directly — there is
    # no `customer` relation on the live model.
    orders_qs = Order.objects.select_related(
        'user', 'pharmacy'
    ).order_by('-created_at')

    # Filter (real status values are Title Case, e.g. 'Pending')
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders_qs = orders_qs.filter(status__iexact=status_filter)

    orders_qs = orders_qs[:100]

    context = {
        'orders': orders_qs,
        'total_orders': Order.objects.count(),
        'pending_count': Order.objects.filter(status__iexact='pending').count(),
        'completed_count': Order.objects.filter(status__iexact='delivered').count(),
        'cancelled_count': Order.objects.filter(status__iexact='cancelled').count(),
    }

    return render(request, 'admin/orders_monitoring.html', context)


@role_required('admin', 'super_admin')
def order_details(request, pk):
    """Order details"""
    from types import SimpleNamespace

    order = get_object_or_404(Order, pk=pk)

    # Template expects order.customer.user.* and order.customer.phone (the
    # shape of the old admin_panel.Customer duplicate). The live Order model
    # links straight to CustomUser via `user` and stores phone directly on
    # the order itself, so build a lightweight compatible shim instead of
    # touching every template line.
    order.customer = SimpleNamespace(user=order.user, phone=order.phone)

    # Order -> OrderItem relation related_name is 'items' in orders/models.py,
    # but keep this defensive in case the project changes.
    items_qs = []
    if hasattr(order, 'items'):
        items_qs = order.items.select_related('product')

        # Template uses item.medicine.name; OrderItem model uses `product`.
        # We alias medicine -> product at the view layer by using a lightweight
        # attribute injection so the template can stay unchanged.
        for oi in items_qs:
            if not hasattr(oi, 'medicine'):
                setattr(oi, 'medicine', oi.product)

    context = {
        'order': order,
        'items': items_qs,
    }

    return render(request, 'admin/order_details.html', context)


# ===== PRESCRIPTION MONITORING =====
@role_required('admin', 'super_admin')
def prescription_monitoring(request):
    """Prescription monitoring page"""

    # customers_d.Prescription.customer/.pharmacy are direct FKs to
    # CustomUser — there is no `.user` sub-relation to select through.
    # Keep prefetch if your Prescription model has an 'items' relation.
    prescriptions = Prescription.objects.select_related(
        'customer', 'pharmacy'
    ).prefetch_related('items__product').order_by('-created_at')

    # Filter (real status values are lowercase: pending/approved/rejected)
    status_filter = request.GET.get('status', '')
    if status_filter:
        prescriptions = prescriptions.filter(status__iexact=status_filter)

    context = {
        'prescriptions': prescriptions,
        'total_count': prescriptions.count(),
        'pending_count': Prescription.objects.filter(status__iexact='pending').count(),
        # Real model has no separate FLAGGED status — flagged prescriptions
        # are stored as 'rejected' (see flag_prescription below), so
        # verified/flagged just mirror approved/rejected here.
        'verified_count': Prescription.objects.filter(status__iexact='approved').count(),
        'flagged_count': Prescription.objects.filter(status__iexact='rejected').count(),
    }
    
    return render(request, 'admin/prescription_monitoring.html', context)


@role_required('admin', 'super_admin')
def verify_prescription(request, pk):
    """Verify prescription"""
    prescription = get_object_or_404(Prescription, pk=pk)
    # Real model status choices are lowercase (pending/approved/rejected)
    # and has no verified_at field.
    prescription.status = 'approved'
    prescription.save()

    AdminActivityLog.objects.create(
        admin=request.user,
        action='PRESCRIPTION_VERIFIED',
        target_model='Prescription',
        target_id=prescription.id,
        description=f'Verified prescription: PRX-{prescription.id}',
        ip_address=get_client_ip(request)
    )

    messages.success(request, f'Prescription PRX-{prescription.id} verified')
    return redirect('admin_panel:prescription_monitoring')


@role_required('admin', 'super_admin')
def flag_prescription(request, pk):
    """Flag prescription"""
    prescription = get_object_or_404(Prescription, pk=pk)
    # No separate FLAGGED status on the real model — reuse 'rejected' and
    # record the reason so it's distinguishable in the activity log.
    prescription.status = 'rejected'
    reason = request.POST.get('reason', '').strip()
    if reason:
        prescription.rejection_reason = reason
    prescription.save()

    AdminActivityLog.objects.create(
        admin=request.user,
        action='PRESCRIPTION_REJECTED',
        target_model='Prescription',
        target_id=prescription.id,
        description=f'Flagged prescription: PRX-{prescription.id}',
        ip_address=get_client_ip(request)
    )

    messages.warning(request, f'Prescription PRX-{prescription.id} has been flagged')
    return redirect('admin_panel:prescription_monitoring')


# ===== PAYMENTS & REVENUE =====
@role_required('admin', 'super_admin')
def _month_bounds(reference, months_ago):
    """Return (start, end) datetimes for the calendar month `months_ago`
    months before `reference` (0 = the current month)."""
    year = reference.year
    month = reference.month - months_ago
    while month <= 0:
        month += 12
        year -= 1
    start = reference.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
    if month == 12:
        end = start.replace(year=year + 1, month=1)
    else:
        end = start.replace(month=month + 1)
    return start, end


@role_required('admin', 'super_admin')
def payments_revenue(request):
    """Payments and revenue page"""
    # Real orders.Payment.status choices are lowercase.
    total_revenue = Payment.objects.filter(status='success').aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Monthly revenue (current calendar month)
    now = timezone.now()
    current_month_start, _ = _month_bounds(now, 0)
    monthly_revenue = Payment.objects.filter(
        status='success',
        created_at__gte=current_month_start
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Pending payouts — payments still sitting in 'pending' status.
    pending_payouts = Payment.objects.filter(status='pending').aggregate(
        total=Sum('amount')
    )['total'] or 0

    # Success rate across all recorded payments.
    total_payment_count = Payment.objects.count()
    success_payment_count = Payment.objects.filter(status='success').count()
    success_rate = (
        round((success_payment_count / total_payment_count) * 100, 1)
        if total_payment_count else 0.0
    )

    # Recent transactions. Order links to the customer via `user` directly.
    recent_transactions = Payment.objects.select_related(
        'order__user'
    ).order_by('-created_at')[:20]

    # Top earning pharmacies — dashboards.Pharmacy has no total_revenue
    # field, so compute it from the live orders (related_name='orders').
    top_pharmacies_qs = Pharmacy.objects.annotate(
        computed_revenue=Sum('orders__total_amount')
    ).filter(computed_revenue__isnull=False, computed_revenue__gt=0).order_by('-computed_revenue')[:5]

    palette = [
        ('teal', 'Verified Vendor'),
        ('orange', 'Top Rated'),
        ('blue', 'Fast Seller'),
        ('purple', 'Rising Star'),
        ('rose', 'Consistent'),
    ]
    top_pharmacies = []
    for idx, ph in enumerate(top_pharmacies_qs):
        parts = [w[0] for w in ph.name.split() if w][:2]
        initials = (''.join(parts) or ph.name[:2]).upper()
        color, default_label = palette[idx % len(palette)]
        top_pharmacies.append({
            'name': ph.name,
            'initials': initials,
            'revenue': ph.computed_revenue or 0,
            'color': color,
            'label': 'Verified Vendor' if ph.is_verified else default_label,
        })

    # Revenue trend — real monthly totals for the last 6 months.
    chart_labels = []
    chart_values = []
    for i in range(5, -1, -1):
        start, end = _month_bounds(now, i)
        total = Payment.objects.filter(
            status='success', created_at__gte=start, created_at__lt=end
        ).aggregate(total=Sum('amount'))['total'] or 0
        chart_labels.append(start.strftime('%b'))
        chart_values.append(float(total))

    context = {
        'total_revenue': total_revenue,
        'monthly_revenue': monthly_revenue,
        'pending_payouts': pending_payouts,
        'success_rate': success_rate,
        'recent_transactions': recent_transactions,
        'top_pharmacies': top_pharmacies,
        'chart_labels': json.dumps(chart_labels),
        'chart_values': json.dumps(chart_values),
    }

    return render(request, 'admin/payments_revenue.html', context)


@role_required('admin', 'super_admin')
def export_payments_csv(request):
    """Export payment transactions as CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="payments_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['Transaction ID', 'Order ID', 'Customer', 'Amount', 'Gateway', 'Status', 'Date'])

    payments = Payment.objects.select_related('order__user').order_by('-created_at')
    for p in payments:
        customer_name = ''
        if p.order and p.order.user:
            customer_name = p.order.user.get_full_name() or p.order.user.email
        writer.writerow([
            p.transaction_id or f'PMT-{p.id}',
            p.order.order_id if p.order else '',
            customer_name,
            p.amount,
            p.gateway,
            p.get_status_display(),
            p.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    AdminActivityLog.objects.create(
        admin=request.user,
        action='PAYMENTS_EXPORTED',
        description='Exported payments & revenue CSV report',
        ip_address=get_client_ip(request),
    )

    return response


# ===== REPORTS & ANALYTICS =====
@role_required('admin', 'super_admin')
def reports_analytics(request):
    """Reports and analytics page"""
    # Metrics are computed from DB (no hardcoded values).
    now = timezone.now()

    # Periods for MoM calculations
    current_start = now - timedelta(days=30)
    previous_start = now - timedelta(days=60)
    previous_end = current_start

    # Platform growth: compare total customers in last 30 days vs previous 30 days.
    # customers_d.Customer has no created_at of its own — use the underlying
    # CustomUser.date_joined instead.
    current_new_customers = Customer.objects.filter(user__date_joined__gte=current_start).count()
    previous_new_customers = Customer.objects.filter(
        user__date_joined__gte=previous_start,
        user__date_joined__lt=previous_end,
    ).count()

    if previous_new_customers > 0:
        growth_pct = ((current_new_customers - previous_new_customers) / previous_new_customers) * 100
    else:
        growth_pct = 100.0 if current_new_customers > 0 else 0.0

    platform_growth = f"{growth_pct:+.0f}%"

    # Order rate: orders per day (last 30 days)
    orders_30d = Order.objects.filter(created_at__gte=current_start).count()
    order_rate = f"{(orders_30d / 30):.0f}/day" if orders_30d else '0/day'

    # Customer retention: ratio of customers with >=2 orders within last 30 days.
    # orders.Order links to the customer via `user` directly (no `customer` FK).
    repeat_customers_qs = (
        Order.objects.filter(created_at__gte=current_start)
        .values('user_id')
        .annotate(order_count=Count('id'))
        .filter(order_count__gte=2)
    )
    repeat_customers = repeat_customers_qs.count()
    total_customers_with_orders = (
        Order.objects.filter(created_at__gte=current_start)
        .values('user_id')
        .distinct()
        .count()
    )

    if total_customers_with_orders > 0:
        retention_pct = (repeat_customers / total_customers_with_orders) * 100
    else:
        retention_pct = 0.0

    customer_retention = f"{retention_pct:.0f}%"

    # Avg order value: avg order total_amount (last 30 days)
    avg_order_value_raw = Order.objects.filter(created_at__gte=current_start).aggregate(avg=Avg('total_amount'))['avg']
    avg_order_value = str(int(avg_order_value_raw)) if avg_order_value_raw is not None else '0'

    # ----- Top Selling Medicines (real, from OrderItem) -----
    top_medicines_qs = (
        OrderItem.objects
        .values('product__name')
        .annotate(units_sold=Sum('quantity'), revenue=Sum(F('quantity') * F('price')))
        .order_by('-units_sold')[:5]
    )
    top_medicines_qs = list(top_medicines_qs)
    max_units = max([m['units_sold'] or 0 for m in top_medicines_qs], default=0)
    top_medicines = []
    for m in top_medicines_qs:
        units = m['units_sold'] or 0
        pct = round((units / max_units) * 100) if max_units else 0
        top_medicines.append({
            'name': m['product__name'] or 'Unknown',
            'units_sold': units,
            'revenue': m['revenue'] or 0,
            'pct': pct,
        })

    # ----- City-wise Demand Analysis (real, from Order -> Pharmacy.city) -----
    city_current = (
        Order.objects.filter(created_at__gte=current_start, pharmacy__isnull=False)
        .values('pharmacy__city')
        .annotate(revenue=Sum('total_amount'), order_count=Count('id'))
        .order_by('-revenue')[:5]
    )
    city_previous = {
        row['pharmacy__city']: row['revenue'] or 0
        for row in Order.objects.filter(
            created_at__gte=previous_start, created_at__lt=previous_end, pharmacy__isnull=False
        ).values('pharmacy__city').annotate(revenue=Sum('total_amount'))
    }
    city_current = list(city_current)
    max_city_revenue = max([c['revenue'] or 0 for c in city_current], default=0)
    city_demand = []
    for c in city_current:
        city_name = c['pharmacy__city'] or 'Unknown'
        revenue = c['revenue'] or 0
        prev_revenue = city_previous.get(c['pharmacy__city'], 0)
        if prev_revenue:
            change_pct = ((revenue - prev_revenue) / prev_revenue) * 100
        else:
            change_pct = 100.0 if revenue else 0.0
        pct = round((revenue / max_city_revenue) * 100) if max_city_revenue else 0
        city_demand.append({
            'city': city_name,
            'revenue': revenue,
            'order_count': c['order_count'],
            'change_pct': f"{change_pct:+.0f}%",
            'is_up': change_pct >= 0,
            'pct': pct,
        })

    context = {
        'platform_growth': platform_growth,
        'order_rate': order_rate,
        'customer_retention': customer_retention,
        'avg_order_value': avg_order_value,
        'top_medicines': top_medicines,
        'city_demand': city_demand,
    }

    return render(request, 'admin/reports_analytics.html', context)


@role_required('admin', 'super_admin')
def export_reports_csv(request):
    """Export a top-line analytics report as CSV (top medicines + city demand)."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="analytics_report.csv"'

    writer = csv.writer(response)

    writer.writerow(['Top Selling Medicines'])
    writer.writerow(['Medicine', 'Units Sold', 'Revenue'])
    top_medicines_qs = (
        OrderItem.objects
        .values('product__name')
        .annotate(units_sold=Sum('quantity'), revenue=Sum(F('quantity') * F('price')))
        .order_by('-units_sold')[:20]
    )
    for m in top_medicines_qs:
        writer.writerow([m['product__name'] or 'Unknown', m['units_sold'] or 0, m['revenue'] or 0])

    writer.writerow([])
    writer.writerow(['City-wise Demand'])
    writer.writerow(['City', 'Orders', 'Revenue'])
    city_qs = (
        Order.objects.filter(pharmacy__isnull=False)
        .values('pharmacy__city')
        .annotate(revenue=Sum('total_amount'), order_count=Count('id'))
        .order_by('-revenue')[:20]
    )
    for c in city_qs:
        writer.writerow([c['pharmacy__city'] or 'Unknown', c['order_count'], c['revenue'] or 0])

    AdminActivityLog.objects.create(
        admin=request.user,
        action='REPORT_EXPORTED',
        description='Exported reports & analytics CSV report',
        ip_address=get_client_ip(request),
    )

    return response


# ===== NOTIFICATIONS =====
@role_required('admin', 'super_admin')
def notifications(request):
    """Notifications page"""
    # Fetch recent notifications first, then mark the admin's unread as read.
    notifications_list = list(Notification.objects.order_by('-created_at')[:20])
    total_sent = Notification.objects.count()

    # Mark this admin's own targeted (SPECIFIC recipient) notifications as
    # read, so the sidebar/bell badge count actually goes down after
    # visiting this page — mirrors the same fix applied to the
    # customer/pharmacy notification pages.
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)

    context = {
        'notifications': notifications_list,
        'total_sent': total_sent,
    }
    
    return render(request, 'admin/notifications.html', context)


@role_required('admin', 'super_admin')
def send_notification(request):
    """Send notification"""
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        recipient_type = request.POST.get('recipients', 'ALL')
        notification_type = request.POST.get('notif_type', 'ANNOUNCEMENT')
        is_urgent = request.POST.get('is_urgent') == 'on'
        
        Notification.objects.create(
            title=title,
            content=content,
            recipient_type=recipient_type,
            notification_type=notification_type.upper(),
            is_urgent=is_urgent
        )
        
        AdminActivityLog.objects.create(
            admin=request.user,
            action='NOTIFICATION_SENT',
            description=f'Sent notification: {title}',
            ip_address=get_client_ip(request)
        )
        
        messages.success(request, 'Notification sent successfully')
    
    return redirect('admin_panel:notifications')


# ===== SYSTEM SETTINGS =====
@role_required('admin', 'super_admin')
def system_settings(request):
    """System settings page"""
    settings, created = SystemSettings.objects.get_or_create(pk=1)
    
    context = {
        'settings': settings,
    }
    
    return render(request, 'admin/system_settings.html', context)


@role_required('admin', 'super_admin')
def update_settings(request):
    """Update system settings — validated so bad input never crashes the page."""
    if request.method != 'POST':
        return redirect('admin_panel:system_settings')

    settings_obj, created = SystemSettings.objects.get_or_create(pk=1)
    errors = []

    platform_name = request.POST.get('platform_name', '').strip()
    if not platform_name:
        errors.append('Platform name cannot be empty.')

    support_email = request.POST.get('support_email', '').strip()
    email_regex = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not support_email or not re.match(email_regex, support_email):
        errors.append('Please enter a valid support email address.')

    support_phone = request.POST.get('support_phone', '').strip()
    platform_version = request.POST.get('platform_version', '').strip()

    validity_days_raw = request.POST.get('validity_days', '').strip()
    try:
        validity_days = int(validity_days_raw)
        if validity_days < 1 or validity_days > 3650:
            errors.append('License validity period must be between 1 and 3650 days.')
    except (TypeError, ValueError):
        errors.append('License validity period must be a whole number of days.')
        validity_days = None

    commission_raw = request.POST.get('commission', '').strip()
    try:
        commission = float(commission_raw)
        if commission < 0 or commission > 100:
            errors.append('Platform commission must be between 0 and 100%.')
    except (TypeError, ValueError):
        errors.append('Platform commission must be a valid number.')
        commission = None

    min_order_raw = request.POST.get('min_order', '').strip()
    try:
        min_order = float(min_order_raw)
        if min_order < 0:
            errors.append('Minimum order amount cannot be negative.')
    except (TypeError, ValueError):
        errors.append('Minimum order amount must be a valid number.')
        min_order = None

    if errors:
        for err in errors:
            messages.error(request, err)

        AdminActivityLog.objects.create(
            admin=request.user,
            action='SETTINGS_UPDATE_FAILED',
            description='Attempted settings update failed validation: ' + '; '.join(errors),
            ip_address=get_client_ip(request),
        )
        return redirect('admin_panel:system_settings')

    settings_obj.platform_name = platform_name
    settings_obj.support_email = support_email
    settings_obj.support_phone = support_phone
    settings_obj.platform_version = platform_version or settings_obj.platform_version
    settings_obj.auto_verify_license = request.POST.get('auto_verify') == 'on'
    settings_obj.manual_review_required = request.POST.get('manual_review') == 'on'
    settings_obj.license_validity_days = validity_days
    settings_obj.terms_and_conditions = request.POST.get('terms', settings_obj.terms_and_conditions)
    settings_obj.privacy_policy = request.POST.get('privacy', settings_obj.privacy_policy)
    settings_obj.platform_commission = commission
    settings_obj.minimum_order_amount = min_order

    settings_obj.save()

    AdminActivityLog.objects.create(
        admin=request.user,
        action='SETTINGS_UPDATED',
        description='Updated system settings',
        ip_address=get_client_ip(request)
    )

    messages.success(request, 'Settings updated successfully')
    return redirect('admin_panel:system_settings')


def _display_name_for_log_user(user):
    """Friendly display name for a log row (pharmacy name when available)."""
    if not user:
        return 'Unknown'
    pharmacy = getattr(user, 'pharmacy', None)
    if pharmacy and getattr(pharmacy, 'name', None):
        return pharmacy.name
    full_name = user.get_full_name() if hasattr(user, 'get_full_name') else ''
    return full_name or getattr(user, 'email', None) or getattr(user, 'username', 'Unknown')


# ===== SECURITY & LOGS =====
@role_required('admin', 'super_admin')
def security_logs(request):
    """Security logs page — real login activity, suspicious-activity detection
    (repeated failed logins from the same IP, or accounts with repeated
    failures), and a real admin audit feed. Paginated, 10 rows per page."""
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    login_logs_qs = LoginLog.objects.select_related('user').order_by('-created_at')
    paginator = Paginator(login_logs_qs, 10)
    page_number = request.GET.get('page', 1)
    login_logs_page = paginator.get_page(page_number)

    total_logins = LoginLog.objects.filter(status='SUCCESS', created_at__gte=last_24h).count()
    failed_attempts = LoginLog.objects.filter(status='FAILED', created_at__gte=last_24h).count()
    admin_actions_count = AdminActivityLog.objects.filter(created_at__gte=last_7d).count()

    # ----- Suspicious activity detection (real, computed from LoginLog) -----
    suspicious_activity = []

    # 1) Same IP with 3+ failed attempts in the last 24 hours.
    ip_failures = (
        LoginLog.objects.filter(status='FAILED', created_at__gte=last_24h)
        .values('ip_address')
        .annotate(fail_count=Count('id'))
        .filter(fail_count__gte=3)
        .order_by('-fail_count')[:10]
    )
    for row in ip_failures:
        latest = LoginLog.objects.filter(
            status='FAILED', ip_address=row['ip_address'], created_at__gte=last_24h
        ).order_by('-created_at').first()
        suspicious_activity.append({
            'severity': 'High',
            'title': 'Multiple failed login attempts from same IP',
            'user': _display_name_for_log_user(latest.user) if latest else 'Unknown',
            'ip': row['ip_address'],
            'time': latest.created_at if latest else now,
            'detail': f"{row['fail_count']} failed attempts in the last 24 hours",
        })

    # 2) Accounts with 3+ cumulative failed attempts on record (CustomUser.failed_login_attempts).
    from authentication.models import CustomUser
    flagged_users = CustomUser.objects.filter(failed_login_attempts__gte=3).order_by('-last_failed_login')[:10]
    for u in flagged_users:
        suspicious_activity.append({
            'severity': 'Medium',
            'title': 'Account with repeated failed login attempts',
            'user': _display_name_for_log_user(u),
            'ip': '—',
            'time': u.last_failed_login or now,
            'detail': f"{u.failed_login_attempts} failed attempts on record",
        })

    suspicious_activity.sort(key=lambda x: x['time'], reverse=True)
    suspicious_activity = suspicious_activity[:10]

    # ----- Admin audit log (real AdminActivityLog feed) -----
    admin_audit_log = AdminActivityLog.objects.select_related('admin').order_by('-created_at')[:10]

    context = {
        'login_logs': login_logs_page,
        'total_logins': total_logins,
        'failed_attempts': failed_attempts,
        'admin_actions_count': admin_actions_count,
        'suspicious_activity': suspicious_activity,
        'suspicious_count': len(suspicious_activity),
        'admin_audit_log': admin_audit_log,
    }
    
    return render(request, 'admin/security_logs.html', context)


@role_required('admin', 'super_admin')
def export_security_logs_csv(request):
    """Export login activity logs as CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="security_logs_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['User', 'Email Attempted', 'Status', 'IP Address', 'Time', 'Failure Reason'])

    logs = LoginLog.objects.select_related('user').order_by('-created_at')[:1000]
    for log in logs:
        writer.writerow([
            _display_name_for_log_user(log.user),
            log.email_attempted or '',
            log.get_status_display(),
            log.ip_address,
            log.created_at.strftime('%Y-%m-%d %H:%M'),
            log.failure_reason,
        ])

    AdminActivityLog.objects.create(
        admin=request.user,
        action='SECURITY_LOGS_EXPORTED',
        description='Exported security & login logs CSV',
        ip_address=get_client_ip(request),
    )

    return response


@role_required('admin', 'super_admin')
def admin_activity_logs(request):
    """Admin activity logs"""
    logs = AdminActivityLog.objects.select_related('admin').order_by('-created_at')[:100]
    
    context = {
        'logs': logs,
    }
    
    return render(request, 'admin/admin_activity_logs.html', context)


# ===== ERROR HANDLERS =====
def error_404(request, exception):
    """Custom 404 page"""
    return render(request, 'admin/errors/404.html', status=404)


def error_500(request):
    """Custom 500 page"""
    return render(request, 'admin/errors/500.html', status=500)