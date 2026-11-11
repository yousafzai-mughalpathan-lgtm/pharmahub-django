from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone

from .models import AdminActivityLog, Prescription
# BUG FIX: admin_panel.models also defines an orphaned duplicate `Order`
# class. `sender=Order` was binding this signal to that dead model, so it
# never fired for real orders at all (the live model is orders.models.Order,
# used by the actual checkout/order flow) — this alone meant order-status
# notifications never ran, regardless of the instance.customer bug below.
from orders.models import Order
from customers_d.models import CustomerNotification
from dashboards.models import PharmacyNotification

channel_layer = get_channel_layer()

@receiver(post_save, sender=AdminActivityLog)
def activity_log_created(sender, instance, created, **kwargs):
    if created:
        data = {
            'type': 'notify',
            'data': {
                'event': 'admin_activity',
                'action': instance.action,
                'description': instance.description,
                'timestamp': instance.created_at.isoformat(),
            }
        }
        async_to_sync(channel_layer.group_send)('admins', data)

@receiver(post_save, sender=Prescription)
def prescription_flagged(sender, instance, created, **kwargs):
    # notify admins if prescription status becomes FLAGGED
    if instance.status == 'FLAGGED':
        data = {
            'type': 'notify',
            'data': {
                'event': 'prescription_flagged',
                'id': instance.id,
                'prescription_id': instance.prescription_id,
                'customer': instance.customer.user.email,
                'timestamp': instance.updated_at.isoformat(),
            }
        }
        async_to_sync(channel_layer.group_send)('admins', data)

# ===== order status change notifications =====
@receiver(pre_save, sender=Order)
def order_status_changed(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        previous = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return
    if previous.status != instance.status:
        # BUG FIX: Order model has a `user` FK, not `customer` — the old
        # `instance.customer` reference raised AttributeError on every
        # status change, silently crashing this signal (post_save on the
        # Order save still went through since this is pre_save, but the
        # notification/broadcast never ran).
        customer_user = instance.user
        data = {
            'type': 'notify',
            'data': {
                'event': 'order_status_changed',
                'order_id': instance.order_id,
                'new_status': instance.status,
                'customer_id': customer_user.id,
                'pharmacy_id': instance.pharmacy.id if instance.pharmacy else None,
                'timestamp': timezone.now().isoformat(),
            }
        }

        # 1. Persist to the tables the dashboards actually read from —
        # websocket-only push meant nothing showed up unless the tab was
        # open and connected at that exact moment.
        CustomerNotification.objects.create(
            user=customer_user,
            message=f"Your order {instance.order_id} status changed to '{instance.status}'.",
        )
        if instance.pharmacy and instance.pharmacy.user_id:
            PharmacyNotification.objects.create(
                user=instance.pharmacy.user,
                message=f"Order {instance.order_id} status changed to '{instance.status}'.",
                order=instance,
            )

        # 2. Realtime broadcast to relevant groups. Group names must match
        # consumers.py, which groups by the LIVE customers_d.Customer /
        # dashboards.Pharmacy ids (related_name 'customer' / 'pharmacy'),
        # not the raw user id.
        async_to_sync(channel_layer.group_send)('admins', data)
        customer_profile = getattr(customer_user, 'customer', None)
        if customer_profile:
            async_to_sync(channel_layer.group_send)(f'customer_{customer_profile.id}', data)
        if instance.pharmacy:
            async_to_sync(channel_layer.group_send)(f'pharmacy_{instance.pharmacy.id}', data)
