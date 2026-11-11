from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    
    path('add-to-cart-api/',    views.add_to_cart_api,      name='add_to_cart_api'),
    path('clear-and-add/',      views.clear_and_add_cart_api, name='clear_and_add_cart_api'), 
    path('cart/',               views.view_cart,            name='view_cart'),
    path('checkout/',           views.checkout,             name='checkout'),
    path('place-order/',        views.place_order,          name='place_order'),
    path('order-success/',      views.order_success,        name='order_success'),
    path('medicine/',           views.medicine,             name='medicine')
    
]