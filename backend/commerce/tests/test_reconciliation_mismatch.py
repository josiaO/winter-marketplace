"""Reconciliation mismatch detection (no mutation in these tests)."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from commerce.models import Order
from commerce.services.reconciliation import run_reconciliation_scan

User = get_user_model()


class ReconciliationMismatchLogTests(TestCase):
    databases = {'default'}

    @patch('commerce.services.reconciliation._emit_anomaly')
    def test_confirmed_order_without_transaction_logs_mismatch(self, _emit):
        buyer = User.objects.create_user(username='rb', password='pw')
        seller = User.objects.create_user(username='rs', password='pw')
        order = Order.objects.create(
            buyer=buyer,
            seller=seller,
            status='confirmed',
            subtotal=Decimal('10.00'),
            total_amount=Decimal('10.00'),
            shipping_address='addr',
        )
        with patch('commerce.services.reconciliation.logger') as log:
            run_reconciliation_scan(lookback_days=1, auto_fix=False, order_id=order.pk)
        warned = any(
            call.args and call.args[0] == 'RECONCILIATION_MISMATCH'
            for call in log.warning.call_args_list
        )
        self.assertTrue(
            warned,
            msg='Expected RECONCILIATION_MISMATCH warning; got %r' % log.warning.call_args_list,
        )
