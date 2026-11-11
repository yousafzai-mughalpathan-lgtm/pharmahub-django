from django.test import TestCase
from django.contrib.auth import get_user_model
User = get_user_model()

from customers_d.models import Cart, CartItem
from dashboards.models import Medicine, Pharmacy


class CartTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='testuser@example.com', username='testuser', password='pass123', role='customer')
        self.pharmacy_user = User.objects.create_user(email='pharmuser@example.com', username='pharmuser', password='pass123', role='pharmacy')

        # Some projects use Pharmacy model tied to user and is_verified flag
        self.pharmacy = Pharmacy.objects.create(
            user=self.pharmacy_user,
            name='Test Pharmacy',
            is_verified=True
        )

        self.medicine = Medicine.objects.create(
            user=self.pharmacy_user,
            pharmacy=self.pharmacy,
            name='Panadol',
            brand='Panadol',
            category='Painkiller',
            price=35,
            stock_quantity=100,
            expiry_date='2030-01-01',
            batch_number='BATCH-TEST',
            description='Test medicine'
        )

    def test_cart_creation(self):
        cart = Cart.objects.create(user=self.user, is_active=True)
        self.assertEqual(cart.user, self.user)
        self.assertTrue(cart.is_active)

    def test_cart_item_added(self):
        cart = Cart.objects.create(user=self.user, is_active=True)
        item = CartItem.objects.create(cart=cart, product=self.medicine, quantity=2)
        self.assertEqual(cart.items.count(), 1)
        self.assertEqual(item.quantity, 2)

    def test_add_to_cart_api_requires_login(self):
        response = self.client.post(
            '/orders/add-to-cart-api/',
            content_type='application/json',
            data='{"medicine_id": 1, "quantity": 1}'
        )
        # Should redirect to login or return 401/403 depending on settings
        self.assertNotEqual(response.status_code, 200)

    def test_search_medicines_requires_login(self):
        response = self.client.get('/customer_dashboard/search_medicines/')
        self.assertNotEqual(response.status_code, 200)

