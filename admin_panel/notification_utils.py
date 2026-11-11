# admin_panel/notification_utils.py
"""
Central fan-out for admin-sent notifications.

Root cause of "customer/pharmacy ko notification receive nahi hoti":
admin_panel.Notification is its OWN table that only the admin's
Notifications page reads. The customer dashboard reads
customers_d.CustomerNotification and the pharmacy dashboard reads
dashboards.PharmacyNotification — two completely separate tables.
Creating a row in admin_panel.Notification never created matching rows
in those two tables, so nothing ever showed up for the actual
customer/pharmacy, even though the POST request itself succeeded
(hence "request POST ja rahi hai" but nothing arrives).

This module is the single place that, given an admin_panel.Notification
instance, creates the matching CustomerNotification / PharmacyNotification
rows AND pushes a realtime websocket event to the right group.
"""
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from customers_d.models import CustomerNotification
from dashboards.models import PharmacyNotification


def _push_ws(group, payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(group, {'type': 'notify', 'data': payload})
    except Exception as e:
        print(f"WS push failed for group {group}: {e}")


def _notify_customer_user(user, text, ws_payload):
    CustomerNotification.objects.create(user=user, message=text)
    # group name must match consumers.py, which uses the LIVE
    # customers_d.Customer related_name ('customer'), not the orphaned
    # admin_panel duplicate's 'customer_profile'
    customer_profile = getattr(user, 'customer', None)
    if customer_profile:
        _push_ws(f'customer_{customer_profile.id}', ws_payload)


def _notify_pharmacy_user(user, text, ws_payload):
    PharmacyNotification.objects.create(user=user, message=text)
    pharmacy_profile = getattr(user, 'pharmacy', None)
    if pharmacy_profile:
        _push_ws(f'pharmacy_{pharmacy_profile.id}', ws_payload)


def fanout_notification(notification):
    """
    Takes a just-created admin_panel.Notification row and delivers it to
    the actual customer/pharmacy notification tables + realtime channel,
    based on notification.recipient_type.
    """
    from authentication.models import CustomUser  # local import avoids circular import

    text = f"{notification.title}: {notification.content}"
    ws_payload = {
        'event': 'admin_notification',
        'id': notification.id,
        'title': notification.title,
        'message': notification.content,
        'is_urgent': notification.is_urgent,
        'timestamp': notification.created_at.isoformat(),
    }

    recipient_type = notification.recipient_type

    if recipient_type == 'SPECIFIC':
        user = notification.recipient
        if not user:
            return
        if user.role == 'customer':
            _notify_customer_user(user, text, ws_payload)
        elif user.role in ('pharmacy', 'pharmacist'):
            _notify_pharmacy_user(user, text, ws_payload)
        return

    if recipient_type in ('ALL', 'CUSTOMERS'):
        for user in CustomUser.objects.filter(role='customer'):
            _notify_customer_user(user, text, ws_payload)

    if recipient_type in ('ALL', 'PHARMACIES'):
        for user in CustomUser.objects.filter(role__in=['pharmacy', 'pharmacist']):
            _notify_pharmacy_user(user, text, ws_payload)

    if recipient_type == 'VERIFIED_PHARMACIES':
        for user in CustomUser.objects.filter(
            role__in=['pharmacy', 'pharmacist'],
            pharmacy__is_verified=True,
        ):
            _notify_pharmacy_user(user, text, ws_payload)

    # keep other admins' live dashboards in sync too
    _push_ws('admins', ws_payload)
