"""Server-side payment verification helpers."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from escrow_engine.models import Transaction
from escrow_engine.models.transaction import TransactionSource
from escrow_engine.providers.base import PaymentResult
from escrow_engine.services.payment import verify_payment_with_provider
from escrow_engine.state_machine import TransactionStatus as TS

User = get_user_model()


class VerifyPaymentWithProviderTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.u = User.objects.create_user(username='vp', password='pw')
        self.txn = Transaction.objects.create(
            amount=Decimal('10.00'),
            currency='TZS',
            source=TransactionSource.API,
            status=TS.PENDING_PAYMENT,
            buyer_user=self.u,
            payment_method='mobile_money',
        )

    @patch('escrow_engine.services.payment.get_provider')
    def test_pending_calls_provider_query(self, mock_get_provider):
        mock_provider = mock_get_provider.return_value
        mock_provider.query_payment_status.return_value = PaymentResult(
            success=True,
            gateway_reference='G1',
            raw_payload={'x': 1},
        )
        r = verify_payment_with_provider(self.txn)
        self.assertTrue(r.success)
        mock_provider.query_payment_status.assert_called_once()

    def test_hold_short_circuits_without_provider_call(self):
        self.txn.status = TS.HOLD
        self.txn.save(update_fields=['status'])
        with patch('escrow_engine.services.payment.get_provider') as mock_gp:
            r = verify_payment_with_provider(self.txn)
        self.assertTrue(r.success)
        mock_gp.assert_not_called()
