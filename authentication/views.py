# authentication/views.py

import logging
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.utils.html import escape
from .models import CustomUser
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetConfirmView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.urls import reverse_lazy
from .roles import get_default_dashboard_url, is_pharmacy_user
from .forms import PharmaHubPasswordResetForm
from admin_panel.models import LoginLog
from customers_d.models import Customer


def _get_client_ip(request):
    """Get client IP address (handles proxy headers)."""
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip.strip()
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or '0.0.0.0'


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# 1. PASSWORD RESET CONFIRM (auto-login after reset)
# ─────────────────────────────────────────────────────────────────
class MyPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "authentication/password_reset_confirm.html"

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect(get_default_dashboard_url(user))


# ─────────────────────────────────────────────────────────────────
# 2. LOGIN / SIGNUP PAGE
# ─────────────────────────────────────────────────────────────────
def login_signup_view(request):

    # ============================================
    # LOGOUT OLD USER BEFORE GOOGLE LOGIN
    # ============================================
    if request.user.is_authenticated:
        return redirect(get_default_dashboard_url(request.user))

    # ============================================
    # GET PARAMETERS
    # ============================================
    role = request.GET.get('role')
    action = request.GET.get('action')

    # ============================================
    # GOOGLE SIGNUP FLOW
    # ============================================
    if action == 'signup':

        # Role validation
        if role not in ['customer', 'pharmacy']:

            messages.error(
                request,
                'Please select a role before signing up with Google.'
            )

            return redirect('/auth/login-signup/?show=signup')

        # Save role in session
        request.session['selected_role'] = role

        # Save action
        request.session['google_auth_action'] = 'signup'

        # Redirect to Google
        return redirect(
            '/accounts/google/login/?prompt=select_account&approval_prompt=force&access_type=offline'
        )

    # ============================================
    # GOOGLE LOGIN FLOW
    # ============================================
    if action == 'login':

        # Save login action
        request.session['google_auth_action'] = 'login'

        # Redirect to Google
        return redirect(
            '/accounts/google/login/?prompt=select_account&approval_prompt=force&access_type=offline'
        )

    # ============================================
    # NORMAL PAGE LOAD
    # ============================================
    show = request.GET.get('show', 'login')

    return render(
        request,
        'authentication/login_signup.html',
        {
            'show': show
        }
    )


@login_required
def post_auth_redirect(request):
    """Central redirect after any auth flow."""
    return redirect(get_default_dashboard_url(request.user))


# ─────────────────────────────────────────────────────────────────
# 3. SIGNUP
# ─────────────────────────────────────────────────────────────────
def signup_view(request):
    if request.user.is_authenticated:
        logout(request)

    if request.method == 'POST':
        username = request.POST.get('name_or_pharmacy_name', '').strip()
        email    = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        confirm  = request.POST.get('confirm_password', '').strip()
        role     = request.POST.get('signup-role', '').strip()

        # Role validation
        if role not in ('customer', 'pharmacy'):
            messages.error(request, "Please select a role — Customer or Pharmacy.")
            return redirect('/auth/login-signup/?show=signup')

        # Field validation
        errors = []
        if not username or not email or not password:
            errors.append("All fields are required.")
        elif password != confirm:
            errors.append("Passwords do not match.")
        else:
            if len(password) < 8:
                errors.append("Password must be at least 8 characters long.")
            if not re.search(r"[A-Z]", password):
                errors.append("Password must contain at least 1 uppercase letter.")
            if not re.search(r"[0-9]", password):
                errors.append("Password must contain at least 1 number.")
            if not re.search(r'[!@#$%^&*(),.?\":{}|<>]', password):
                errors.append("Password must contain at least 1 special character.")

        if errors:
            for e in errors:
                messages.error(request, e, extra_tags='signup_error')
            return render(request, 'authentication/login_signup.html', {
                'show': 'signup',
                'signup_email': email,
                'signup_name': username,
                'signup_role': role,
            })

        # Email format validation
        email_regex = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            messages.error(request, "Please enter a valid email address (e.g., user@example.com).", extra_tags='signup_error')
            return render(request, 'authentication/login_signup.html', {
                'show': 'signup',
                'signup_email': email,
                'signup_name': username,
                'signup_role': role,
            })

        # Email uniqueness check (email is global — one account per email regardless of role)
        if CustomUser.objects.filter(email__iexact=email).exists():
            messages.error(request, "This email is already registered. Please use a different email.", extra_tags='signup_error')
            return render(request, 'authentication/login_signup.html', {
                'show': 'signup',
                'signup_email': email,
                'signup_name': username,
                'signup_role': role,
            })

        # Create user
        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            is_active=True,
        )

        user.save()

        # customers_d.Customer is the profile row Customer Management / the
        # /api/customers/ endpoint actually query. Without this, a customer
        # signup only ever creates the CustomUser row, so the account shows
        # up in User Management but never in Customer Management.
        if role == 'customer':
            Customer.objects.get_or_create(user=user)

        messages.success(
            request,
            "Account created successfully! Please login to continue.",
            extra_tags='login_success'
        )

        request.session.pop('selected_role', None)

        return redirect('/auth/login-signup/?show=login')

    # GET request fallback
    return redirect('/auth/login-signup/?show=signup')


# ─────────────────────────────────────────────────────────────────
# 4. LOGIN
# ─────────────────────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect(get_default_dashboard_url(request.user))

    if request.method == 'POST':
        email    = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        client_ip = _get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]

        if not email or not password:
            messages.error(request, "Email and password are required.", extra_tags='login_error')
            return redirect('/auth/login-signup/?show=login')

        # Email format validation
        email_regex = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            messages.error(request, "Please enter a valid email address.", extra_tags='login_error')
            return redirect('/auth/login-signup/?show=login')

        user = authenticate(request, email=email, password=password)

        if user is None:
            # Failed login attempt track karo
            db_user = None
            try:
                from django.utils import timezone
                db_user = CustomUser.objects.filter(email__iexact=email).first()
                if db_user:
                    db_user.failed_login_attempts += 1
                    db_user.last_failed_login = timezone.now()
                    db_user.save(update_fields=['failed_login_attempts', 'last_failed_login'])
            except Exception:
                pass

            try:
                LoginLog.objects.create(
                    user=db_user,
                    email_attempted=email,
                    status='FAILED',
                    ip_address=client_ip,
                    user_agent=user_agent,
                    failure_reason='Invalid email or password',
                )
            except Exception:
                logger.exception("Failed to write LoginLog entry for failed login")

            messages.error(request, "Invalid email or password.", extra_tags='login_error')
            return redirect('/auth/login-signup/?show=login')

        # Successful login — reset failed attempts
        if user.failed_login_attempts > 0:
            user.failed_login_attempts = 0
            user.save(update_fields=['failed_login_attempts'])

        login(request, user)

        try:
            LoginLog.objects.create(
                user=user,
                email_attempted=email,
                status='SUCCESS',
                ip_address=client_ip,
                user_agent=user_agent,
                device_info=getattr(user, 'role', ''),
            )
        except Exception:
            logger.exception("Failed to write LoginLog entry for successful login")

        return redirect(get_default_dashboard_url(user))

    return redirect('/auth/login-signup/')


# ─────────────────────────────────────────────────────────────────
# 5. LOGOUT
# ─────────────────────────────────────────────────────────────────
def logout_view(request):
    logout(request)
    return redirect('authentication:login_signup')


# ─────────────────────────────────────────────────────────────────
# 6. ACCOUNT SETTINGS
# ─────────────────────────────────────────────────────────────────
@login_required
def account_settings_view(request):
    return render(request, 'authentication/account_settings.html')


# ─────────────────────────────────────────────────────────────────
# 7. FORGOT PASSWORD (AJAX)
# ─────────────────────────────────────────────────────────────────
@require_POST
def forgot_password_ajax(request):
    email = (request.POST.get('email') or '').strip()
    if not email:
        return JsonResponse({'ok': False, 'message': 'Email is required.'}, status=400)

    if not CustomUser.objects.filter(email__iexact=email, is_active=True).exists():
        return JsonResponse({'ok': False, 'message': 'No active account found with this email.'}, status=404)

    form = PharmaHubPasswordResetForm({'email': email})
    if not form.is_valid():
        return JsonResponse({'ok': False, 'message': 'Please enter a valid email.'}, status=400)

    try:
        form.save(
            request=request,
            use_https=request.is_secure(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            email_template_name='authentication/password_reset_email.html',
        )
    except Exception:
        return JsonResponse({'ok': False, 'message': 'Email sending failed. Please try again.'}, status=500)

    return JsonResponse({'ok': True, 'message': 'Reset link sent. Check your inbox/spam.'})


# ─────────────────────────────────────────────────────────────────
# 8. VERIFICATION PAGE (With Submission Logic)
# ─────────────────────────────────────────────────────────────────
@login_required
def verification_view(request):
    if request.method == 'POST':
        license_number = request.POST.get('license_number')
        license_file = request.FILES.get('license_file')
        
        if license_number and license_file:
            user = request.user
            user.license = license_number
            user.license_document = license_file
            # Note: is_verified_pharmacist ko yahan True nahi karna, 
            # wo admin manually check karke karega.
            user.save()
            messages.success(
                request,
                "license_submitted",
                extra_tags='license_success'
            )
            return redirect('dashboards:pharmacy_home')
            
    return render(request, 'authentication/verification_form.html')