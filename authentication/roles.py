from django.urls import reverse

ADMIN_ROLES = {"admin", "super_admin"}
PHARMACY_ROLES = {"pharmacy", "pharmacist"}
CUSTOMER_ROLES = {"customer"}


def normalize_role(role):
    return (role or "").strip().lower()

def get_user_role(user):
    if not getattr(user, "is_authenticated", False):
        return ""
    return normalize_role(getattr(user, "role", ""))

def is_admin_user(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    return get_user_role(user) in ADMIN_ROLES

def is_pharmacy_user(user):
    if not getattr(user, "is_authenticated", False):
        return False
    return get_user_role(user) in PHARMACY_ROLES

def is_customer_user(user):
    if not getattr(user, "is_authenticated", False):
        return False
    return get_user_role(user) in CUSTOMER_ROLES

def user_has_any_role(user, allowed_roles):
    if not getattr(user, "is_authenticated", False):
        return False
    normalized = {normalize_role(role) for role in allowed_roles}

    if normalize_role("admin") in normalized or normalize_role("super_admin") in normalized:
        if is_admin_user(user):
            return True

    role = get_user_role(user)
    return role in normalized

def get_default_dashboard_url(user):
    if is_admin_user(user):
        return reverse("admin_panel:admin_dashboard")
    if is_pharmacy_user(user):
        return reverse("dashboards:pharmacy_home")
    return reverse("customers_d:customer_home")
