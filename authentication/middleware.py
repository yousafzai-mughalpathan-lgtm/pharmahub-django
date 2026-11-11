from django.shortcuts import redirect
from .roles import is_admin_user, is_customer_user, is_pharmacy_user


class RoleBasedAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if request.user.is_authenticated:

            # ── Admin panel ──────────────────────────────────────────
            if path.startswith('/admin/') and not path.startswith('/admin/login/'):
                if not is_admin_user(request.user):
                    return redirect('/')

            # ── Pharmacy dashboard ────────────────────────────────────
            elif path.startswith('/pharmacy_dashboard/'):
                # Sirf ye check karein ke user login hai aur pharmacy role hai
                if not (is_pharmacy_user(request.user) or is_admin_user(request.user)):
                    return redirect('/')
                # Verification ka check yahan se hata diya gaya hai

            # ── Customer dashboard area ───────────────────────────────
            elif path.startswith('/customer_dashboard/'):
                # ✅ FIX: Yeh paths sab logged-in users ke liye hain
                # (cart, orders, checkout - pharmacy bhi use kare)
                SHARED_PATHS = (
                    '/customer_dashboard/my-orders/',
                    '/customer_dashboard/order/',
                    '/customer_dashboard/cart/',
                    '/customer_dashboard/checkout/',
                    '/customer_dashboard/place-order/',
                    '/customer_dashboard/order-success/',
                    '/customer_dashboard/add-to-cart/',
                    '/customer_dashboard/add-to-cart-api/',
                    '/customer_dashboard/cart-count/',
                    '/customer_dashboard/update-cart-item/',
                )
                is_shared = any(path.startswith(p) for p in SHARED_PATHS)

                if not is_shared:
                    # Sirf customer-only pages block karo pharmacy ke liye
                    if not (is_customer_user(request.user) or is_admin_user(request.user)):
                        return redirect('/')

        response = self.get_response(request)
        return response