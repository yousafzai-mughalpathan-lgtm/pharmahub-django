from functools import wraps
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages  # ✅ Correct Django import
from .roles import get_default_dashboard_url, user_has_any_role

def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(settings.LOGIN_URL)
            if not user_has_any_role(request.user, allowed_roles):
                return redirect(get_default_dashboard_url(request.user))
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator

def verification_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        # FIX: 'pharmacy' role ka verification 'dashboards.Pharmacy.is_verified' se hota hai
        # (admin_panel.approve_pharmacy isi field ko set karta hai). 'is_verified_pharmacist'
        # alag flag hai jo sirf role='pharmacist' staff accounts ke liye set hota hai
        # (admin_panel.approve_pharmacist). Pehle 'pharmacy' role ke liye bhi 'is_verified_pharmacist'
        # check ho raha tha jo us role ke liye kabhi True set hi nahi hota — isliye pharmacy account
        # admin approval ke bawajood hamesha locked reh jata tha (jese naya ho).
        if request.user.role == 'pharmacy':
            pharmacy = getattr(request.user, 'pharmacy', None)
            if not pharmacy or not pharmacy.is_verified:
                messages.info(request, "Please verify your license to access Inventory management.")
                return redirect('authentication:verification_view')
        elif request.user.role == 'pharmacist' and not request.user.is_verified_pharmacist:
            messages.info(request, "Please verify your license to access Inventory management.")
            return redirect('authentication:verification_view')
        return view_func(request, *args, **kwargs)
    return wrapped