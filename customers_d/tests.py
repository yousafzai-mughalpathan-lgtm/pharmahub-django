from django.test import TestCase
from django.contrib.auth import get_user_model

from customers_d.models import Cart
from dashboards.models import Pharmacy, Medicine

User = get_user_model()


class CustomersDTests(TestCase):
    def test_customer_can_create_cart(self):
        user = User.objects.create_user(
            email='cust@example.com',
            username='cust',
            password='pass123',
        )
        cart = Cart.objects.create(user=user, is_active=True)
        self.assertEqual(cart.user, user)
        self.assertTrue(cart.is_active)

    def test_verified_pharmacy_filtering(self):
        pharmacy_user = User.objects.create_user(
            email='pharm@example.com',
            username='pharm',
            password='pass123',
        )
        verified_pharmacy = Pharmacy.objects.create(
            user=pharmacy_user,
            name='Verified Pharmacy',
            is_verified=True,
        )

        Pharmacy.objects.create(
            user=User.objects.create_user(
                email='pharm2@example.com',
                username='pharm2',
                password='pass123',
            ),
            name='Unverified Pharmacy',
            is_verified=False,
        )

        self.assertEqual(Pharmacy.objects.filter(is_verified=True).count(), 1)
        self.assertEqual(Pharmacy.objects.filter(is_verified=True).first(), verified_pharmacy)

    def test_medicine_creation(self):
        pharmacy_user = User.objects.create_user(
            email='pharm@example.com',
            username='pharm',
            password='pass123',
        )
        pharmacy = Pharmacy.objects.create(
            user=pharmacy_user,
            name='Test Pharmacy',
            is_verified=True,
        )
        medicine = Medicine.objects.create(
            user=pharmacy_user,
            pharmacy=pharmacy,
            name='Ibuprofen',
            price=50,
            stock_quantity=10,
            expiry_date='2030-01-01',
            batch_number='BATCH-TEST',
            description='Test medicine',
            category='Painkiller',
        )
        self.assertEqual(medicine.name, 'Ibuprofen')
        self.assertEqual(medicine.stock_quantity, 10)

    def test_medicine_out_of_stock_quantity(self):
        pharmacy_user = User.objects.create_user(
            email='pharm@example.com',
            username='pharm',
            password='pass123',
        )
        pharmacy = Pharmacy.objects.create(
            user=pharmacy_user,
            name='Test Pharmacy',
            is_verified=True,
        )
        medicine = Medicine.objects.create(
            user=pharmacy_user,
            pharmacy=pharmacy,
            name='ExpiredMed',
            price=10,
            stock_quantity=0,
            expiry_date='2030-01-01',
            batch_number='BATCH-TEST',
            description='Test medicine',
            category='Painkiller',
        )
        self.assertEqual(medicine.stock_quantity, 0)

