from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin panel configuration for CustomUser model"""

    list_display = ('email', 'username', 'first_name', 'last_name', 'role',
                    'is_verified_pharmacist', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_staff', 'is_active', 'is_superuser', 'is_verified_pharmacist')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        (_('Personal Info'), {'fields': ('first_name', 'last_name')}),
        (_('Role Information'), {'fields': ('role',)}),
        (_('Pharmacy Info'), {'fields': ('license', 'license_document', 'is_verified_pharmacist')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Security'), {'fields': ('last_login_ip', 'failed_login_attempts', 'last_failed_login')}),
        (_('Important Dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'role'),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj and obj.role != 'pharmacy':
            fieldsets = tuple(fs for fs in fieldsets if fs[0] != _('Pharmacy Info'))
        return fieldsets

    def save_model(self, request, obj, form, change):
        # ✅ Superuser bante waqt role automatically admin set ho
        if obj.is_superuser:
            obj.role = 'admin'

        # Non-pharmacy users ki license fields clear karein
        if obj.role not in ('pharmacy', 'pharmacist'):
            obj.license = ''

        super().save_model(request, obj, form, change)
