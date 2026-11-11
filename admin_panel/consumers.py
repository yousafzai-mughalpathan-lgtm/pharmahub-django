from channels.generic.websocket import AsyncWebsocketConsumer
import json

class NotifyConsumer(AsyncWebsocketConsumer):
    """Websocket consumer that joins users to groups based on their role.
    Admins -> 'admins'
    Customers -> 'customer_<id>'
    Pharmacies/Pharmacists -> 'pharmacy_<id>'
    """
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close()
            return

        groups = []
        if getattr(user, 'is_admin_user', False) or user.is_staff:
            groups.append('admins')
        if getattr(user, 'is_customer_user', False):
            try:
                # BUG FIX: `user.customer_profile` pointed at the orphaned
                # admin_panel duplicate Customer model, whose id never
                # matches the LIVE customers_d.Customer id that signals.py
                # and notification_utils.py broadcast to. The live
                # relation's related_name is 'customer'.
                groups.append(f'customer_{user.customer.id}')
            except Exception:
                pass
        if getattr(user, 'is_pharmacist_user', False):
            try:
                # Same bug: live relation's related_name is 'pharmacy',
                # not the orphaned 'pharmacy_profile'.
                groups.append(f'pharmacy_{user.pharmacy.id}')
            except Exception:
                pass

        for grp in groups:
            await self.channel_layer.group_add(grp, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # remove from all groups
        # we don't know which groups were added, but leaving them is okay
        pass

    async def notify(self, event):
        await self.send(text_data=json.dumps(event['data']))
