"""Payment webhook audit, payout disburse amount, OTP logging, throttling."""
from copy import deepcopy
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from escrow_engine.models import PaymentLink, PaymentRecord, Payout, Transaction
from escrow_engine.models.transaction import TransactionSource
from escrow_engine.providers.base import PaymentResult
from escrow_engine.services.payment import handle_webhook
from escrow_engine.services.payout import process_payout
from escrow_engine.state_machine import TransactionStatus

User = get_user_model()


class WebhookPaymentRecordTests(TestCase):
    databases = {'default'}

    def test_failed_verify_writes_payment_record(self):
        before = PaymentRecord.objects.count()
        out = handle_webhook({'status': 'FAILED', 'reference': 'ghost-ref'}, payment_method='selcom')
        self.assertIsNone(out)
        self.assertEqual(PaymentRecord.objects.count(), before + 1)
        row = PaymentRecord.objects.order_by('-pk').first()
        self.assertEqual(row.status, PaymentRecord.Status.FAILED)
        self.assertIn('webhook_verify', row.failure_reason)

    def test_unknown_transaction_writes_orphan_record(self):
        before = PaymentRecord.objects.count()
        out = handle_webhook(
            {'status': 'SUCCESS', 'reference': 'no-such-gateway-ref-xyz'},
            payment_method='selcom',
        )
        self.assertIsNone(out)
        self.assertEqual(PaymentRecord.objects.count(), before + 1)
        row = PaymentRecord.objects.order_by('-pk').first()
        self.assertIsNone(row.transaction)
        self.assertEqual(row.failure_reason, 'webhook_unknown_transaction')


class ProcessPayoutDisburseAmountTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.seller = User.objects.create_user(username='payout_seller', password='pw')
        self.buyer = User.objects.create_user(username='payout_buyer', password='pw')
        self.txn = Transaction.objects.create(
            amount=Decimal('999.00'),
            currency='TZS',
            source=TransactionSource.API,
            status=TransactionStatus.RELEASED,
            buyer_user=self.buyer,
            seller_user=self.seller,
            payment_method='selcom',
        )
        self.payout = Payout.objects.create(
            transaction=self.txn,
            seller=self.seller,
            amount=Decimal('42.50'),
            currency='TZS',
            status=Payout.Status.PENDING,
            payout_method='mpesa',
        )

    @patch('escrow_engine.services.payout.get_provider')
    def test_disburse_receives_payout_amount_not_transaction_amount(self, mock_get_provider):
        mock_provider = MagicMock()
        mock_provider.disburse.return_value = PaymentResult(
            success=True,
            gateway_reference='gw-1',
        )
        mock_get_provider.return_value = mock_provider

        process_payout(self.payout)

        mock_provider.disburse.assert_called_once()
        kwargs = mock_provider.disburse.call_args.kwargs
        self.assertEqual(kwargs.get('amount'), Decimal('42.50'))


class OTPLogTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(username='link_seller', password='pw')
        self.txn = Transaction.objects.create(
            amount=Decimal('5.00'),
            currency='TZS',
            source=TransactionSource.API,
            status=TransactionStatus.CREATED,
            seller_user=self.seller,
        )
        self.link = PaymentLink.objects.create(
            transaction=self.txn,
            created_by=self.seller,
            expires_at=timezone.now() + timezone.timedelta(hours=48),
        )

    def test_request_otp_does_not_log_secret_code(self):
        import logging

        url = reverse('engine-link-request-otp', kwargs={'token': self.link.token})
        with self.assertLogs('escrow_engine.views', level='INFO') as captured:
            r = self.client.post(url, {'phone': '255712345678'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.link.refresh_from_db()
        self.assertTrue(self.link.otp_code)
        blob = '\n'.join(captured.output)
        self.assertNotIn(self.link.otp_code, blob)


class PaymentLinkThrottleTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(username='th_seller', password='pw')
        self.txn = Transaction.objects.create(
            amount=Decimal('5.00'),
            currency='TZS',
            source=TransactionSource.API,
            status=TransactionStatus.CREATED,
            seller_user=self.seller,
        )
        self.link = PaymentLink.objects.create(
            transaction=self.txn,
            created_by=self.seller,
            expires_at=timezone.now() + timezone.timedelta(hours=48),
        )

    def test_otp_endpoint_throttles_after_limit(self):
        rf = deepcopy(settings.REST_FRAMEWORK)
        rf['DEFAULT_THROTTLE_RATES'] = {
            **rf['DEFAULT_THROTTLE_RATES'],
            'escrow_payment_link': '1/minute',
        }
        url = reverse('engine-link-request-otp', kwargs={'token': self.link.token})

        with override_settings(REST_FRAMEWORK=rf):
            r1 = self.client.post(url, {'phone': '255700000001'}, format='json')
            r2 = self.client.post(url, {'phone': '255700000002'}, format='json')

        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 429)
