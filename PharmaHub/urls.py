"""
URL configuration for PharmaHub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('django-admin/', admin.site.urls, name='django_admin'),
    path('admin/', include('admin_panel.urls')),
    path('api/', include('api.api_urls')),
    path('', include('pharmacy.urls')),    
    # Dashboards (Ab sirf ek baar)
    # namespace dashboards so {% url 'dashboards:...' %} works reliably
    path('pharmacy_dashboard/', include(('dashboards.urls', 'dashboards'), namespace='dashboards')),
    # Authentication (Sirf ek baar)
    path('auth/', include('authentication.urls')),    
    # Google Login (allauth)
    path('accounts/', include('allauth.urls')), 
    # Customer Dashboard
    path('customer_dashboard/', include(('customers_d.urls', 'customers_d'), namespace='customers_d')),
    # Pages
    path('pages/', include('pages.urls')), 
    # Admin Panel
    path('', RedirectView.as_view(url='/admin/dashboard/', permanent=False)),
    # Orders (Admin order management)
    path('orders/', include('orders.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# Custom error handlers (optional)
handler404 = 'admin_panel.views.error_404'
handler500 = 'admin_panel.views.error_500'
