from django.urls import path
from . import views
# App name define karna zaroori hai template tags ke liye
app_name = 'customers_d'
urlpatterns = [
    # ── Dashboard Pages ──
    path('', views.customer_dashboard,  name='customer_dashboard'),
    path('home/',               views.customer_home,        name='customer_home'),
    path('search_medicines/',   views.search_medicines,     name='search_medicines'),
    path('symptom_checker/',    views.symptom_checker,      name='symptom_checker'),
    path('my-orders/',          views.my_orders,            name='my_orders'), # Sirf ye ek baar rakhein
    path('nearby_pharmacies/',  views.nearby_pharmacies,    name='nearby_pharmacies'),
    path('upload_prescription/',views.upload_prescription,  name='upload_prescription'),
    path('medicine/',           views.customer_medicine,    name='customer_medicine'),
    # customers_d/urls.py mein ye add karein:
    path('notifications/', views.notification_c_view, name='notification_c'),
    path('prescription-details/<int:prx_id>/', views.prescription_details_view, name='prescription_details'),
    # ── Cart ──
    path('add-to-cart/',        views.add_to_cart,          name='add_to_cart'),
    path('add-to-cart-api/',    views.add_to_cart,          name='add_to_cart_api'),  # orders app se aane wale requests ke liye alias
    path('cart-count/',         views.get_cart_count,       name='get_cart_count'),
    path('cart/',               views.cart_view,            name='cart_view'),
    path('update-cart-item/',   views.update_cart_item,     name='update_cart_item'),
    # ── Checkout Flow ──
    # checkout, place-order, and order-success are handled by the orders app
    # ── AI / Reports ──
    path('predict/',            views.predict_symptom,      name='predict_symptom'),
    path('download-report/<str:disease_name>/', views.download_report, name='download_report'),
    # ── Order Details ──
    # Is path se aap har order ki alag detail dekh sakein ge
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('reorder/<int:order_id>/', views.reorder, name='reorder'),  # Reorder ke liye bhi alag path
    path('cancel/<int:order_id>/', views.cancel_order, name='cancel_order'),

    path('get-quote-details/<int:prx_id>/', views.get_quote_details, name='get_quote_details'),
    # customers_d/urls.py mein ye line add karein

    path('api/notifications/clear-all/', views.clear_customer_notifications_api, name='clear_customer_notifications'),
    
]