from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Category
from listings.models import Listing
from commerce.models import Order
from commerce.services import cart_service as cart_svc
from escrow_engine.models import Transaction


User = get_user_model()


class CommerceOrderFlowTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user(username="buyer_flow", password="pw")
        self.seller = User.objects.create_user(username="seller_flow", password="pw")
        self.cat = Category.objects.create(name="FlowCat", slug="flowcat")
        self.listing = Listing.objects.create(
            owner=self.seller,
            category=self.cat,
            title="Item",
            description="",
            price=Decimal("100.00"),
            status="active",
            is_published=True,
            track_inventory=False,
        )

    @patch("commerce.views.should_open_payment_gateway", return_value=False)
    def test_checkout_creates_order_and_linked_transaction(self, _mock_gateway):
        cart = cart_svc.get_or_create_cart(user=self.buyer)
        cart_svc.add_to_cart(cart=cart, listing_id=self.listing.id, quantity=1)

        self.client.force_authenticate(user=self.buyer)
        res = self.client.post(
            "/api/v1/commerce/cart/checkout/",
            data={
                "shipping_address": "Test Address 123",
                "shipping_method": "standard",
                "payment_method": "mobile_money",
            },
            format="json",
        )
        self.assertIn(res.status_code, (200, 201), res.data)

        order_id = res.data["id"] if isinstance(res.data, dict) else res.data[0]["id"]
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.buyer_id, self.buyer.id)
        self.assertEqual(order.seller_id, self.seller.id)
        self.assertEqual(order.status, "pending")

        txn = Transaction.objects.filter(linked_order=order).first()
        self.assertIsNotNone(txn)

    def test_seller_can_ship_order(self):
        order = Order.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            status="pending",
            subtotal=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            shipping_address="Addr",
            shipping_method="standard",
        )

        self.client.force_authenticate(user=self.seller)
        res = self.client.post(
            f"/api/v1/commerce/orders/{order.id}/ship_order/",
            data={"tracking_number": "TRK-1"},
            format="multipart",
        )
        self.assertEqual(res.status_code, 200, res.data)
        order.refresh_from_db()
        self.assertEqual(order.status, "shipped")
        self.assertEqual(order.tracking_number, "TRK-1")

    def test_buyer_can_confirm_receipt_after_shipped(self):
        order = Order.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            status="shipped",
            subtotal=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            shipping_address="Addr",
            shipping_method="standard",
            tracking_number="TRK-2",
        )

        self.client.force_authenticate(user=self.buyer)
        res = self.client.post(f"/api/v1/commerce/orders/{order.id}/confirm_receipt/", data={}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        order.refresh_from_db()
        self.assertEqual(order.status, "completed")

