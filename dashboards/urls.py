from django.urls import path
from . import views


app_name = 'dashboards'

urlpatterns = [
    # Dashboard main page
    path('', views.pharmacy_dashboard, name='pharmacy_dashboard'),
    # Inventory CRUD
    path('inventory/add_edit/', views.add_edit_medicine, name='add_edit_medicine'),
    path('inventory/delete/<int:pk>/', views.delete_medicine, name='delete_medicine'),
    path('inventory/delete-all/', views.delete_all_medicines, name='delete_all_medicines'),
    path('inventory/get_data/<int:pk>/', views.get_medicine_data, name='get_medicine_data'),
    path('submit-verification/', views.submit_verification, name='submit_verification'),

    # Dashboard home (optional)
    path('home/', views.pharmacy_home, name='pharmacy_home'),
        # Customer-accessible pages
    path('medicine/', views.customer_medicine, name='customer_medicine'),
    path('about/', views.customer_about, name='customer_about'),
    path('pharmacies/', views.customer_pharmacies, name='customer_pharmacies'),
    path('contact/', views.customer_contact, name='customer_contact'),
    path('notifications/', views.pharmacy_notifications, name='pharmacy_notifications'),
    path('inventory/bulk-upload/', views.bulk_upload_medicine, name='bulk_upload_medicine'),
    path('inventory/download-template/', views.download_inventory_template, name='download_inventory_template'),
    path('prescription/reject/<int:pk>/', views.reject_prescription, name='reject_prescription'),
    path('prescription/review/<int:pk>/', views.review_prescription, name='review_prescription'),
    path('order/<str:order_id>/<str:action>/', views.change_order_status, name='change_order_status'),
    path('orders/<str:order_id>/json/', views.get_order_details_api, name='get_order_details_api'),
    path('api/notifications/clear-all/', views.clear_all_notifications_api, name='clear_all_notifications'),
]