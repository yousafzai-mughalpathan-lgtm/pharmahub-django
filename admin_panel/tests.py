from django.test import TestCase
from django.urls import reverse
from django.core import mail
from django.contrib.auth import get_user_model

from .models import Pharmacy, AdminActivityLog

User = get_user_model()


class PharmacyApprovalTests(TestCase):
    def setUp(self):
        # create admin user
        self.admin = User.objects.create_user(
            email='admin@example.com',
            username='admin',
            password='secret',
            role='admin',
            is_staff=True
        )
        # create pharmacy user and profile
        self.pharmacy_user = User.objects.create_user(
            email='pharm@example.com',
            username='pharm',
            password='secret',
            role='pharmacy'
        )
        self.pharmacy = Pharmacy.objects.create(
            user=self.pharmacy_user,
            name='Test Pharmacy',
            owner_name='John Doe',
            email='pharm@example.com',
            phone='1234567890',
            address='123 Street',
            location='City',
            license_number='LIC001'
        )

    def test_approve_sends_email_and_creates_log(self):
        self.client.login(username='admin@example.com', password='secret')
        response = self.client.post(
            reverse('admin_panel:approve_pharmacy', args=[self.pharmacy.id])
        )
        self.pharmacy.refresh_from_db()
        self.assertTrue(self.pharmacy.is_verified)
        # an email should have been sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('approved', mail.outbox[0].subject.lower())
        # log entry present
        self.assertTrue(AdminActivityLog.objects.filter(action='PHARMACY_APPROVED').exists())

    def test_reject_sends_email_and_creates_log(self):
        self.client.login(username='admin@example.com', password='secret')
        response = self.client.post(
            reverse('admin_panel:reject_pharmacy', args=[self.pharmacy.id])
        )
        self.pharmacy.refresh_from_db()
        self.assertFalse(self.pharmacy.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('rejected', mail.outbox[0].subject.lower() or '')
        self.assertTrue(AdminActivityLog.objects.filter(action='PHARMACY_REJECTED').exists())


from django.test import TransactionTestCase

class WebsocketNotificationTests(TransactionTestCase):
    """Simple tests for the websocket consumer for all roles"""
    def setUp(self):
        self.admin = User.objects.create_user(
            email='socketadmin@example.com',
            username='socketadmin',
            password='secret',
            role='admin',
            is_staff=True
        )

    async def test_admin_socket_accepts(self):
        try:
            from channels.testing import WebsocketCommunicator
        except ImportError:
            self.skipTest("daphne not installed, skipping websocket test")
            return
        from PharmaHub.asgi import application
        communicator = WebsocketCommunicator(application, "/ws/notifications/")
        communicator.scope['user'] = self.admin
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()


class OrderNotificationTests(TransactionTestCase):
    def setUp(self):
        # create necessary users and objects
        self.admin = User.objects.create_user(
            email='orderadmin@example.com',
            username='orderadmin',
            password='secret',
            role='admin',
            is_staff=True
        )
        self.customer_user = User.objects.create_user(
            email='cust@example.com',
            username='cust',
            password='secret',
            role='customer'
        )
        from admin_panel.models import Customer, Pharmacy, Order
        self.customer = Customer.objects.create(user=self.customer_user, phone='123')
        self.pharmacy_user = User.objects.create_user(
            email='pharm@example.com',
            username='pharm',
            password='secret',
            role='pharmacy'
        )
        self.pharmacy = Pharmacy.objects.create(
            user=self.pharmacy_user,
            name='Pharm', owner_name='Owner', email='pharm@example.com',
            phone='123', address='addr', location='loc', license_number='L03'
        )
        self.order = Order.objects.create(
            order_id='ORD1',
            customer=self.customer,
            pharmacy=self.pharmacy,
            status='PENDING',
            total_amount=100,
            delivery_address='here'
        )

    async def test_order_status_change_notifies_admin(self):
        try:
            from channels.testing import WebsocketCommunicator
        except ImportError:
            self.skipTest("daphne not installed, skipping websocket test")
            return
        from PharmaHub.asgi import application
        communicator = WebsocketCommunicator(application, "/ws/notifications/")
        communicator.scope['user'] = self.admin
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        # change status
        self.order.status = 'DELIVERED'
        self.order.save()
        message = await communicator.receive_json_from()
        self.assertEqual(message.get('event'), 'order_status_changed')
        self.assertEqual(message.get('order_id'), 'ORD1')
        await communicator.disconnect()


class PharmacistApprovalTests(TestCase):
    """Test pharmacist license verification flow"""
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com',
            username='admin',
            password='secret',
            role='admin',
            is_staff=True
        )
        self.pharmacist = User.objects.create_user(
            email='pharmacist@example.com',
            username='pharm_user',
            password='secret',
            role='pharmacist',
            license='PH-2024-001'
        )

    def test_pharmacist_approval_updates_status(self):
        self.client.login(username='admin@example.com', password='secret')
        response = self.client.post(
            reverse('admin_panel:approve_pharmacist', args=[self.pharmacist.id])
        )
        self.pharmacist.refresh_from_db()
        self.assertTrue(self.pharmacist.is_verified_pharmacist)
        self.assertTrue(self.pharmacist.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('approved', mail.outbox[0].subject.lower())

    def test_pharmacist_rejection_disables_account(self):
        self.client.login(username='admin@example.com', password='secret')
        response = self.client.post(
            reverse('admin_panel:reject_pharmacist', args=[self.pharmacist.id])
        )
        self.pharmacist.refresh_from_db()
        self.assertFalse(self.pharmacist.is_active)
        self.assertEqual(len(mail.outbox), 1)


class UserManagementTests(TestCase):
    """Test admin user management features"""
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com',
            username='admin',
            password='secret',
            role='admin',
            is_staff=True
        )
        self.customer = User.objects.create_user(
            email='customer@example.com',
            username='cust',
            password='secret',
            role='customer',
            is_active=True
        )

    def test_admin_can_disable_user(self):
        self.client.login(username='admin@example.com', password='secret')
        response = self.client.post(
            reverse('admin_panel:toggle_user_active', args=[self.customer.id])
        )
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)
        # check activity log
        self.assertTrue(AdminActivityLog.objects.filter(action='USER_DISABLED').exists())

    def test_admin_can_enable_user(self):
        self.customer.is_active = False
        self.customer.save()
        self.client.login(username='admin@example.com', password='secret')
        response = self.client.post(
            reverse('admin_panel:toggle_user_active', args=[self.customer.id])
        )
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)
        self.assertTrue(AdminActivityLog.objects.filter(action='USER_ENABLED').exists())

    def test_user_management_page_accessible(self):
        self.client.login(username='admin@example.com', password='secret')
        response = self.client.get(reverse('admin_panel:user_management'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'user-management')

    def test_user_management_filters_search_and_role(self):
        # create additional users to test filtering
        User.objects.create_user(email='foo@example.com', password='foo', role='customer')
        User.objects.create_user(email='bar@pharm.com', password='bar', role='pharmacy')
        self.client.login(username='admin@example.com', password='secret')
        # search by email substring
        resp = self.client.get(reverse('admin_panel:user_management') + '?q=foo')
        self.assertContains(resp, 'foo@example.com')
        self.assertNotContains(resp, 'bar@pharm.com')
        # filter by role
        resp = self.client.get(reverse('admin_panel:user_management') + '?role=pharmacy')
        self.assertContains(resp, 'bar@pharm.com')
        self.assertNotContains(resp, 'foo@example.com')
        # filter by status inactive
        self.customer.is_active = False
        self.customer.save()
        resp = self.client.get(reverse('admin_panel:user_management') + '?status=inactive')
        self.assertContains(resp, 'customer@example.com')
        self.assertNotContains(resp, 'admin@example.com')

