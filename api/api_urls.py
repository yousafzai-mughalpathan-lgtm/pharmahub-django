"""
PHARMAHUB - API URLs
Complete REST API Endpoint Configuration
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

# Router for ViewSets
router = DefaultRouter()
router.register(r'pharmacies', views.PharmacyViewSet, basename='pharmacy')
router.register(r'customers', views.CustomerViewSet, basename='customer')
router.register(r'medicines', views.MedicineViewSet, basename='medicine')
router.register(r'medicine-categories', views.MedicineCategoryViewSet, basename='medicine-category')
router.register(r'orders', views.OrderViewSet, basename='order')
router.register(r'prescriptions', views.PrescriptionViewSet, basename='prescription')
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'admin-logs', views.AdminActivityLogViewSet, basename='admin-log')
router.register(r'login-logs', views.LoginLogViewSet, basename='login-log')
router.register(r'settings', views.SystemSettingsViewSet, basename='settings')
router.register(r'users', views.UserViewSet, basename='user')

app_name = 'api'

urlpatterns = [
    # ===== AUTHENTICATION =====
    path('auth/login/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/register/', views.UserRegistrationView.as_view(), name='register'),
    path('auth/pharmacy-register/', views.PharmacyRegistrationView.as_view(), name='pharmacy_register'),
    
    # ===== ADMIN DASHBOARD =====
    path('dashboard/stats/', views.DashboardStatsView.as_view(), name='dashboard_stats'),
    
    # ===== ROUTER ENDPOINTS =====
    path('', include(router.urls)),
]

"""
API ENDPOINTS DOCUMENTATION
============================

AUTHENTICATION:
---------------
POST   /api/auth/login/                  - Login (get JWT tokens)
POST   /api/auth/refresh/                - Refresh access token
POST   /api/auth/register/               - Register new user
POST   /api/auth/pharmacy-register/      - Register pharmacy

ADMIN DASHBOARD:
----------------
GET    /api/dashboard/stats/             - Dashboard statistics

PHARMACIES:
-----------
GET    /api/pharmacies/                  - List all pharmacies
POST   /api/pharmacies/                  - Create pharmacy (Admin)
GET    /api/pharmacies/{id}/             - Get pharmacy details
PUT    /api/pharmacies/{id}/             - Update pharmacy (Admin)
DELETE /api/pharmacies/{id}/             - Delete pharmacy (Admin)
POST   /api/pharmacies/{id}/approve/     - Approve pharmacy (Admin)
POST   /api/pharmacies/{id}/reject/      - Reject pharmacy (Admin)
POST   /api/pharmacies/{id}/suspend/     - Suspend pharmacy (Admin)

Filters:
?status=pending/approved/rejected
?city=Mumbai
?search=keyword

CUSTOMERS:
----------
GET    /api/customers/                   - List all customers (Admin)
GET    /api/customers/{id}/              - Get customer details (Admin)
PUT    /api/customers/{id}/              - Update customer (Admin)
POST   /api/customers/{id}/block/        - Block customer (Admin)
POST   /api/customers/{id}/unblock/      - Unblock customer (Admin)

Filters:
?status=active/blocked
?search=keyword

MEDICINES:
----------
GET    /api/medicines/                   - List all medicines
POST   /api/medicines/                   - Create medicine (Admin)
GET    /api/medicines/{id}/              - Get medicine details
PUT    /api/medicines/{id}/              - Update medicine (Admin)
DELETE /api/medicines/{id}/              - Delete medicine (Admin)

Filters:
?category=1
?search=keyword

MEDICINE CATEGORIES:
--------------------
GET    /api/medicine-categories/         - List categories
POST   /api/medicine-categories/         - Create category (Admin)
GET    /api/medicine-categories/{id}/    - Get category
PUT    /api/medicine-categories/{id}/    - Update category (Admin)
DELETE /api/medicine-categories/{id}/    - Delete category (Admin)

ORDERS:
-------
GET    /api/orders/                      - List orders (filtered by role)
POST   /api/orders/                      - Create order (Customer)
GET    /api/orders/{id}/                 - Get order details
POST   /api/orders/{id}/update_status/   - Update order status

Filters:
?status=pending/confirmed/delivered

PRESCRIPTIONS:
--------------
GET    /api/prescriptions/               - List prescriptions (filtered by role)
POST   /api/prescriptions/               - Upload prescription
GET    /api/prescriptions/{id}/          - Get prescription details
POST   /api/prescriptions/{id}/verify/   - Verify prescription (Admin)
POST   /api/prescriptions/{id}/flag/     - Flag prescription (Admin)

Filters:
?status=pending/verified/flagged

NOTIFICATIONS:
--------------
GET    /api/notifications/               - List notifications
POST   /api/notifications/               - Send notification (Admin)
GET    /api/notifications/{id}/          - Get notification

ADMIN LOGS:
-----------
GET    /api/admin-logs/                  - Admin activity logs
GET    /api/login-logs/                  - Login attempt logs

SYSTEM SETTINGS:
----------------
GET    /api/settings/                    - Get settings (Admin)
PUT    /api/settings/{id}/               - Update settings (Admin)

COMMON QUERY PARAMETERS:
------------------------
?page=1              - Pagination
?page_size=10        - Items per page
?ordering=created_at - Sort by field
?search=keyword      - Search
"""
