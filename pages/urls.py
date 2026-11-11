from django.urls import path
from . import views

app_name = 'pages'  # <- ye namespace define karta hai

urlpatterns = [
    path('medicines/', views.medicine, name='medicine'),  # view name match karo
    path('pharmacies/', views.pharmacies, name='pharmacies'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('help/', views.help, name='help'),
   
# ... aapke purane paths yahan hain ...
    path('privacy-policy/', views.privacy_policy, name='privacy'),
    path('terms-of-service/', views.terms_of_service, name='terms'),
    path('pharmacy/shop/<int:pharmacy_id>/', views.view_shop, name='view_shop'),
    
]
