"""
PHARMAHUB - Custom Permissions
Role-based Access Control for API
"""

from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    """
    Permission for Super Admin and Admin only
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ['super_admin', 'admin']
        )

class IsPharmacist(permissions.BasePermission):
    """
    Permission for Pharmacist users
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ['pharmacist', 'pharmacy']
        )

class IsCustomer(permissions.BasePermission):
    """
    Permission for Customer users
    """
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'customer'
        )

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission for owner of object or admin
    """
    def has_object_permission(self, request, view, obj):
        # Admin can access everything
        if request.user.role in ['super_admin', 'admin']:
            return True
        
        # Check if user is owner
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False

class IsPharmacyOwner(permissions.BasePermission):
    """
    Permission for pharmacy owner
    """
    def has_object_permission(self, request, view, obj):
        if request.user.role in ['super_admin', 'admin']:
            return True
        
        if request.user.role in ['pharmacist', 'pharmacy']:
            return obj.pharmacy == request.user.pharmacy_profile
        
        return False
