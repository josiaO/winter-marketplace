from django.test import TestCase
from django.contrib.auth.models import User
from .views import _serialize_current_user
from commerce.models import Order

class RedirectLogicTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testbuyer', email='test@example.py', password='password123')
        self.seller = User.objects.create_user(username='testseller', email='seller@example.py', password='password123')

    def test_serialize_user_includes_orders_count(self):
        # Initial count should be 0
        data = _serialize_current_user(self.user)
        self.assertEqual(data['user']['orders_count'], 0)
        
        # Create an order
        Order.objects.create(
            buyer=self.user,
            seller=self.seller,
            status='pending',
            total_amount=1000
        )
        
        # New count should be 1
        data = _serialize_current_user(self.user)
        self.assertEqual(data['user']['orders_count'], 1)

