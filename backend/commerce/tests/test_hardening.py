"""Commerce production-hardening regression tests."""
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from catalog.models import Category
from commerce.models import CommissionRule, Order, OrderAuditLog
from commerce.services.lifecycle import OrderLifecycleManager
from commerce.services.payment_return import confirm_marketplace_payment_return
from escrow_engine.models import Transaction
from escrow_engine.services.payment import confirm_payment
from escrow_engine.models.transaction import TransactionSource
from escrow_engine.providers.base import PaymentResult
from escrow_engine.state_machine import PaymentConfirmationSource, TransactionStatus as TS
from listings.models import Listing
from commerce.services.checkout import OrderService
from commerce.services.inventory import InventoryService
from commerce.services import cart_service as cart_svc

User = get_user_model()


class PaymentReturnFraudTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.buyer = User.objects.create_user(username='buyer1', password='pw')
        self.seller = User.objects.create_user(username='seller1', password='pw')
        self.order = Order.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            status='pending',
            subtotal=Decimal('100.00'),
            total_amount=Decimal('100.00'),
        )
        self.txn = Transaction.objects.create(
            amount=Decimal('100.00'),
            currency='TZS',
            source=TransactionSource.MARKETPLACE,
            status=TS.PENDING_PAYMENT,
            buyer_user=self.buyer,
            seller_user=self.seller,
            payment_method='mobile_money',
            gateway_reference='GW-1',
        )
        self.txn.link_order(self.order)

    @patch('commerce.services.payment_return.verify_payment_with_provider')
    def test_fake_client_success_does_not_confirm_without_provider(self, mock_verify):
        mock_verify.return_value = PaymentResult(success=False, error='provider_says_unpaid')
        with self.assertRaises(ValidationError):
            confirm_marketplace_payment_return(
                user=self.buyer,
                transaction_reference=self.txn.reference,
                raw_request_meta={'status': 'SUCCESS', 'payment_status': 'PAID'},
            )
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, TS.PENDING_PAYMENT)

    @patch('commerce.services.payment_return.confirm_payment')
    @patch('commerce.services.payment_return.verify_payment_with_provider')
    def test_provider_success_confirms(self, mock_verify, mock_confirm):
        mock_verify.return_value = PaymentResult(
            success=True,
            gateway_reference='GW-1',
            raw_payload={'ok': True},
        )
        mock_confirm.return_value = self.txn
        out = confirm_marketplace_payment_return(
            user=self.buyer,
            transaction_reference=self.txn.reference,
            raw_request_meta={},
        )
        self.assertIs(mock_confirm.called, True)
        _, kwargs = mock_confirm.call_args
        self.assertEqual(kwargs.get('confirmation_source'), PaymentConfirmationSource.PROVIDER_VERIFY)
        self.assertEqual(out, self.txn)

    @patch('commerce.services.payment_return.confirm_payment')
    def test_return_url_idempotent_when_already_hold(self, mock_confirm):
        # Bypass FSM on save(): PENDING_PAYMENT → HOLD must go through PAID in production code.
        Transaction.objects.filter(pk=self.txn.pk).update(status=TS.HOLD)
        self.txn.refresh_from_db()
        out = confirm_marketplace_payment_return(
            user=self.buyer,
            transaction_reference=self.txn.reference,
            raw_request_meta={'status': 'SUCCESS'},
        )
        mock_confirm.assert_not_called()
        self.assertEqual(out.pk, self.txn.pk)


class ConfirmPaymentEnforcementTests(TestCase):
    databases = {'default'}

    def test_provider_verify_requires_payload(self):
        buyer = User.objects.create_user(username='bpv', password='pw')
        seller = User.objects.create_user(username='spv', password='pw')
        order = Order.objects.create(
            buyer=buyer,
            seller=seller,
            status='pending',
            subtotal=Decimal('10.00'),
            total_amount=Decimal('10.00'),
        )
        txn = Transaction.objects.create(
            amount=Decimal('10.00'),
            currency='TZS',
            source=TransactionSource.MARKETPLACE,
            status=TS.PENDING_PAYMENT,
            buyer_user=buyer,
            seller_user=seller,
            payment_method='mobile_money',
        )
        txn.link_order(order)
        with self.assertRaises(ValueError):
            confirm_payment(
                txn,
                gateway_reference='GW',
                raw_payload={'return_meta': {}},
                confirmation_source=PaymentConfirmationSource.PROVIDER_VERIFY,
            )


class ReconciliationScanTests(TestCase):
    databases = {'default'}

    def test_run_reconciliation_scan_runs(self):
        from commerce.services.reconciliation import run_reconciliation_scan

        stats = run_reconciliation_scan(lookback_days=7, auto_fix=False)
        self.assertIn('orders_scanned', stats)
        self.assertIn('errors', stats)


class OrderBulkUpdateGuardTests(TestCase):
    databases = {'default'}

    def test_queryset_update_status_forbidden(self):
        buyer = User.objects.create_user(username='bbu', password='pw')
        seller = User.objects.create_user(username='sbu', password='pw')
        order = Order.objects.create(
            buyer=buyer,
            seller=seller,
            status='pending',
            subtotal=Decimal('1.00'),
            total_amount=Decimal('1.00'),
        )
        with self.assertRaises(RuntimeError):
            Order.objects.filter(pk=order.pk).update(status='confirmed')


class OrderStatusGuardTests(TestCase):
    databases = {'default'}

    def test_direct_status_mutation_raises(self):
        buyer = User.objects.create_user(username='bg', password='pw')
        seller = User.objects.create_user(username='sg', password='pw')
        order = Order.objects.create(
            buyer=buyer,
            seller=seller,
            status='pending',
            subtotal=Decimal('1.00'),
            total_amount=Decimal('1.00'),
        )
        order.status = 'confirmed'
        with self.assertRaises(DjangoValidationError):
            order.save()


class CancellationAuditTests(TestCase):
    databases = {'default'}

    def test_orderservice_cancel_uses_lifecycle_and_escrow_path(self):
        buyer = User.objects.create_user(username='b2', password='pw')
        seller = User.objects.create_user(username='s2', password='pw')
        order = Order.objects.create(
            buyer=buyer,
            seller=seller,
            status='pending',
            subtotal=Decimal('10.00'),
            total_amount=Decimal('10.00'),
        )
        OrderService.cancel_order(order)
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertTrue(
            OrderAuditLog.objects.filter(order=order, action='cancel_order').exists()
        )


class CommissionRuleTests(TestCase):
    databases = {'default'}

    def test_category_rule_over_global(self):
        cat = Category.objects.create(
            name='Phones',
            slug=f'phones-hardening-{uuid.uuid4().hex[:10]}',
        )
        CommissionRule.objects.create(
            name='global',
            rule_type='percentage',
            percentage_value=Decimal('10.00'),
            priority=1,
            is_active=True,
            category=None,
        )
        CommissionRule.objects.create(
            name='phones',
            rule_type='percentage',
            percentage_value=Decimal('3.00'),
            priority=5,
            is_active=True,
            category=cat,
        )
        seller = User.objects.create_user(username='sl', password='pw')
        listing = Listing.objects.create(
            owner=seller,
            category=cat,
            title='Phone',
            description='',
            price=Decimal('1000.00'),
            status='active',
            is_published=True,
            track_inventory=False,
        )
        fee = OrderService.calculate_platform_fee(listing, Decimal('1000.00'))
        self.assertEqual(fee, Decimal('30.00'))

    def test_same_priority_prefers_category_rule(self):
        cat = Category.objects.create(
            name='Gadgets',
            slug=f'gadgets-hardening-{uuid.uuid4().hex[:10]}',
        )
        CommissionRule.objects.create(
            name='global_p2',
            rule_type='percentage',
            percentage_value=Decimal('10.00'),
            priority=2,
            is_active=True,
            category=None,
        )
        CommissionRule.objects.create(
            name='gadget_p2',
            rule_type='percentage',
            percentage_value=Decimal('4.00'),
            priority=2,
            is_active=True,
            category=cat,
        )
        seller = User.objects.create_user(username='sl3', password='pw')
        listing = Listing.objects.create(
            owner=seller,
            category=cat,
            title='G',
            description='',
            price=Decimal('500.00'),
            status='active',
            is_published=True,
            track_inventory=False,
        )
        fee = OrderService.calculate_platform_fee(listing, Decimal('1000.00'))
        self.assertEqual(fee, Decimal('40.00'))


class InventoryReservationTests(TestCase):
    databases = {'default'}

    def test_second_reserve_fails_when_out_of_stock(self):
        seller = User.objects.create_user(username='sl2', password='pw')
        listing = Listing.objects.create(
            owner=seller,
            title='Limited',
            description='',
            price=Decimal('50.00'),
            status='active',
            is_published=True,
            track_inventory=True,
            stock_quantity=1,
            allow_backorders=False,
        )
        r1 = InventoryService.reserve_stock(listing, 1)
        self.assertIsNotNone(r1)
        listing.refresh_from_db()
        r2 = InventoryService.reserve_stock(listing, 1)
        self.assertIsNone(r2)


class CartCrossUserStockTests(TestCase):
    databases = {'default'}

    def test_second_buyer_cannot_claim_stock_already_in_another_cart(self):
        seller = User.objects.create_user(username='csell', password='pw')
        b1 = User.objects.create_user(username='cb1', password='pw')
        b2 = User.objects.create_user(username='cb2', password='pw')
        listing = Listing.objects.create(
            owner=seller,
            title='Single',
            description='',
            price=Decimal('10.00'),
            status='active',
            is_published=True,
            track_inventory=True,
            stock_quantity=1,
            allow_backorders=False,
        )
        cart1 = cart_svc.get_or_create_cart(b1)
        cart2 = cart_svc.get_or_create_cart(b2)
        cart_svc.add_to_cart(cart1, listing.id, quantity=1)
        with self.assertRaises(ValueError) as ctx:
            cart_svc.add_to_cart(cart2, listing.id, quantity=1)
        self.assertIn('stock', str(ctx.exception).lower())


class OrderApiPermissionTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user(username='bb', password='pw')
        self.seller = User.objects.create_user(username='ss', password='pw')
        self.order = Order.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            status='completed',
            subtotal=Decimal('1.00'),
            total_amount=Decimal('1.00'),
        )

    def test_post_orders_collection_not_allowed(self):
        self.client.force_authenticate(self.buyer)
        r = self.client.post('/api/v1/commerce/orders/', {}, format='json')
        self.assertEqual(r.status_code, 405)

    def test_process_payout_requires_admin(self):
        self.client.force_authenticate(self.seller)
        r = self.client.post(f'/api/v1/commerce/orders/{self.order.pk}/process/', {}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_seller_cannot_review_buyer_order(self):
        txn = Transaction.objects.create(
            amount=Decimal('1.00'),
            currency='TZS',
            source=TransactionSource.MARKETPLACE,
            status=TS.RELEASED,
            buyer_user=self.buyer,
            seller_user=self.seller,
            payment_method='mobile_money',
        )
        txn.link_order(self.order)
        self.client.force_authenticate(self.seller)
        r = self.client.post(
            f'/api/v1/commerce/orders/{self.order.pk}/review/',
            {'rating': 5, 'comment': 'x'},
            format='json',
        )
        self.assertEqual(r.status_code, 403)


class ConfirmDeliveryCommandTests(TestCase):
    databases = {'default'}

    def test_confirm_delivery_transitions(self):
        buyer = User.objects.create_user(username='cb', password='pw')
        seller = User.objects.create_user(username='cs', password='pw')
        order = Order.objects.create(
            buyer=buyer,
            seller=seller,
            status='shipped',
            subtotal=Decimal('1.00'),
            total_amount=Decimal('1.00'),
        )
        OrderLifecycleManager.confirm_delivery(order, actor=None)
        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')
