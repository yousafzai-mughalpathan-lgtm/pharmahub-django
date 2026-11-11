from django.contrib import admin

from .models import Cart, CartItem, Customer, Prescription, PrescriptionItem, QuoteItem, CustomerNotification

admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Customer)
admin.site.register(Prescription)
admin.site.register(PrescriptionItem)
admin.site.register(QuoteItem)
admin.site.register(CustomerNotification)


