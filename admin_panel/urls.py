"""
PHARMAHUB - Admin Panel URLs
Routes for Custom Admin UI Templates
"""

from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # ===== AUTHENTICATION =====
    path('auth/', RedirectView.as_view(pattern_name='admin_panel:admin_login', permanent=False)),
    path('login/', views.admin_login, name='admin_login'),
    path('logout/', views.admin_logout, name='admin_logout'),
    
path('', RedirectView.as_view(pattern_name='admin_panel:admin_dashboard', permanent=False)),

    # ===== DASHBOARD =====
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # ===== PHARMACY MANAGEMENT =====
    path('pharmacy-verification/', views.pharmacy_verification, name='pharmacy_verification'),
    path('pharmacy-verification/<int:pk>/approve/', views.approve_pharmacy, name='approve_pharmacy'),
    path('pharmacy-verification/<int:pk>/reject/', views.reject_pharmacy, name='reject_pharmacy'),
    
    path('pharmacy-management/', views.pharmacy_management, name='pharmacy_management'),
    path('pharmacy/<int:pk>/suspend/', views.suspend_pharmacy, name='suspend_pharmacy'),
    path('pharmacy/<int:pk>/activate/', views.activate_pharmacy, name='activate_pharmacy'),
    path('pharmacy/<int:pk>/update-location/', views.update_pharmacy_location, name='update_pharmacy_location'),
   
    
    # ===== PHARMACIST MANAGEMENT =====
    path('pharmacist-verification/', views.pharmacist_verification, name='pharmacist_verification'),
    path('pharmacist/<int:pk>/approve/', views.approve_pharmacist, name='approve_pharmacist'),
    path('pharmacist/<int:pk>/reject/', views.reject_pharmacist, name='reject_pharmacist'),

    # ===== USER MANAGEMENT =====
    path('user-management/', views.user_management, name='user_management'),
    path('user/<int:pk>/detail/', views.user_detail, name='user_detail'),
    path('user/<int:pk>/toggle-active/', views.toggle_user_active, name='toggle_user_active'),
    path('user/<int:pk>/edit-role/', views.edit_user_role, name='edit_user_role'),
    path('user/<int:pk>/delete/', views.delete_user, name='delete_user'),
    path('users/export-csv/', views.export_users_csv, name='export_users_csv'),

    # ===== CUSTOMER MANAGEMENT =====
    path('customer-management/', views.customer_management, name='customer_management'),
    path('customer/<int:pk>/block/', views.block_customer, name='block_customer'),
    path('customer/<int:pk>/unblock/', views.unblock_customer, name='unblock_customer'),
    
    # ===== MEDICINE CONTROL =====
    path('medicine-control/', views.medicine_control, name='medicine_control'),
    path('medicine-category/add/', views.add_medicine_category, name='add_medicine_category'),
    path('medicine/<int:pk>/ban/', views.ban_medicine, name='ban_medicine'),
    path('medicine/<int:pk>/unban/', views.unban_medicine, name='unban_medicine'),
    
    # ===== ORDERS =====
    path('orders-monitoring/', views.orders_monitoring, name='orders_monitoring'),
    path('order/<int:pk>/details/', views.order_details, name='order_details'),
    
    # ===== PRESCRIPTIONS =====
    path('prescription-monitoring/', views.prescription_monitoring, name='prescription_monitoring'),
    path('prescription/<int:pk>/verify/', views.verify_prescription, name='verify_prescription'),
    path('prescription/<int:pk>/flag/', views.flag_prescription, name='flag_prescription'),
    
    # ===== PAYMENTS & REVENUE =====
    path('payments-revenue/', views.payments_revenue, name='payments_revenue'),
    path('payments-revenue/export-csv/', views.export_payments_csv, name='export_payments_csv'),
    
    # ===== REPORTS & ANALYTICS =====
    path('reports-analytics/', views.reports_analytics, name='reports_analytics'),
    path('reports-analytics/export-csv/', views.export_reports_csv, name='export_reports_csv'),
    
    # ===== NOTIFICATIONS =====
    path('notifications/', views.notifications, name='notifications'),
    path('notification/send/', views.send_notification, name='send_notification'),
    
    # ===== SYSTEM SETTINGS =====
    path('system-settings/', views.system_settings, name='system_settings'),
    path('system-settings/update/', views.update_settings, name='update_settings'),
    
    # ===== SECURITY & LOGS =====
    path('security-logs/', views.security_logs, name='security_logs'),
    path('security-logs/export-csv/', views.export_security_logs_csv, name='export_security_logs_csv'),
    path('admin-activity-logs/', views.admin_activity_logs, name='admin_activity_logs'),
]
