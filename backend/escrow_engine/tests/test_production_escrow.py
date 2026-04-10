"""Production hardening: GatewayEvent idempotency, payout recovery, developer API extras."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from escrow_engine.models import APIKey, GatewayEvent, Payout, Transaction
from escrow_engine.models.api_key import hash_api_key
from escrow_engine.models.transaction import TransactionSource
from escrow_engine.services.payment import handle_webhook, upsert_gateway_webhook_event
from escrow_engine.state_machine import TransactionStatus
from escrow_engine.tasks import recover_stuck_payouts

User = get_user_model()


class GatewayWebhookIdempotencyTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.buyer = User.objects.create_user(username='gw_buyer', password='pw')
        self.seller = User.objects.create_user(username='gw_seller', password='pw')
        self.txn = Transaction.objects.create(
            amount=Decimal('100.00'),
            currency='TZS',
            source=TransactionSource.API,
            status=TransactionStatus.PENDING_PAYMENT,
            buyer_user=self.buyer,
            seller_user=self.seller,
            gateway_reference='gw-ref-idem-1',
            payment_method='selcom',
        )

    def test_same_webhook_payload_creates_one_gateway_event(self):
        payload = {'status': 'SUCCESS', 'reference': 'gw-ref-idem-1'}
        ge1, c1 = upsert_gateway_webhook_event('selcom', payload)
        ge2, c2 = upsert_gateway_webhook_event('selcom', payload)
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(ge1.pk, ge2.pk)
        self.assertEqual(GatewayEvent.objects.filter(provider='selcom').count(), 1)

    @patch('escrow_engine.services.payment.escrow_distributed_lock')
    def test_handle_webhook_second_call_short_circuits_processed(self, mock_lock):
        cm = MagicMock()
        cm.__enter__.return_value = True
        cm.__exit__.return_value = None
        mock_lock.return_value = cm

        payload = {'status': 'SUCCESS', 'reference': 'gw-ref-idem-1'}
        t1 = handle_webhook(payload, payment_method='selcom')
        self.assertIsNotNone(t1)
        self.assertEqual(t1.status, TransactionStatus.HOLD)

        t2 = handle_webhook(payload, payment_method='selcom')
        self.assertIsNotNone(t2)
        ge = GatewayEvent.objects.get(provider='selcom')
        self.assertEqual(ge.status, GatewayEvent.Status.PROCESSED)


class RecoverStuckPayoutsTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.seller = User.objects.create_user(username='rec_seller', password='pw')
        self.buyer = User.objects.create_user(username='rec_buyer', password='pw')
        self.txn = Transaction.objects.create(
            amount=Decimal('50.00'),
            currency='TZS',
            source=TransactionSource.API,
            status=TransactionStatus.RELEASED,
            buyer_user=self.buyer,
            seller_user=self.seller,
        )
        self.payout = Payout.objects.create(
            transaction=self.txn,
            seller=self.seller,
            amount=Decimal('50.00'),
            currency='TZS',
            status=Payout.Status.PROCESSING,
            payout_method='mpesa',
        )

    def test_recovery_marks_old_processing_as_failed(self):
        Payout.objects.filter(pk=self.payout.pk).update(
            updated_at=timezone.now() - timedelta(hours=2),
        )
        recover_stuck_payouts()
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, Payout.Status.FAILED)
        self.assertIn('recovery', self.payout.failure_reason.lower())


class DeveloperAPIKeyHardeningTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.client = APIClient()
        self.raw = 'rotate-test-secret'
        self.key = APIKey.objects.create(
            name='rot-key',
            key_hash=hash_api_key(self.raw),
            is_active=True,
            scopes=['read', 'write', 'pay', 'refund', 'release'],
        )

    def test_expired_key_rejected(self):
        APIKey.objects.filter(pk=self.key.pk).update(
            expires_at=timezone.now() - timedelta(days=1),
        )
        url = reverse('dev-transaction-list')
        r = self.client.get(url, HTTP_X_API_KEY=self.raw)
        self.assertEqual(r.status_code, 401)

    def test_rotate_endpoint_returns_new_secret(self):
        # Mounted at /api/v1/escrow/dev/ (see backend.urls + escrow_engine.urls).
        r = self.client.post(
            '/api/v1/escrow/dev/keys/rotate/',
            {},
            HTTP_X_API_KEY=self.raw,
        )
        self.assertEqual(r.status_code, 201)
        self.assertIn('secret', r.data)
        self.key.refresh_from_db()
        self.assertFalse(self.key.is_active)
        self.assertEqual(APIKey.objects.filter(is_active=True).count(), 1)


class SelcomWebhookHttpSecurityTests(TestCase):
    databases = {'default'}

    @override_settings(DEBUG=False, ESCROW_WEBHOOK_INSECURE_SKIP_VERIFY=False)
    def test_post_without_signature_headers_returns_403(self):
        url = reverse('engine-webhook-selcom')
        client = APIClient()
        r = client.post(url, {'reference': 'x'}, format='json')
        self.assertEqual(r.status_code, 403)

    @override_settings(DEBUG=True, ESCROW_WEBHOOK_INSECURE_SKIP_VERIFY=True)
    def test_insecure_skip_allows_processing_without_hmac(self):
        url = reverse('engine-webhook-selcom')
        client = APIClient()
        r = client.post(url, {'status': 'FAILED', 'reference': 'no-txn-ref'}, format='json')
        self.assertIn(r.status_code, (200, 400, 500))
        self.assertNotEqual(r.status_code, 403)
