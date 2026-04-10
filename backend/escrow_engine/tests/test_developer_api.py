"""Developer API (X-Api-Key) security and scoping."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from escrow_engine.models import APIKey, Transaction
from escrow_engine.models.api_key import hash_api_key
from escrow_engine.models.transaction import TransactionSource
from escrow_engine.state_machine import TransactionStatus


User = get_user_model()


class DeveloperAPIKeyTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.client = APIClient()
        self.raw_secret = 'unit-test-secret-please-change'
        self.api_key = APIKey.objects.create(
            name='test-key',
            key_hash=hash_api_key(self.raw_secret),
            is_active=True,
            scopes=['read', 'write', 'pay', 'refund', 'release'],
        )

    def _headers(self):
        return {'HTTP_X_API_KEY': self.raw_secret}

    def test_missing_key_returns_403(self):
        url = reverse('dev-transaction-list')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 403)

    def test_invalid_key_returns_401(self):
        url = reverse('dev-transaction-list')
        r = self.client.get(url, HTTP_X_API_KEY='not-a-valid-key')
        self.assertEqual(r.status_code, 401)

    def test_list_only_own_transactions(self):
        other_key = APIKey.objects.create(
            name='other',
            key_hash=hash_api_key('other-secret'),
            is_active=True,
            scopes=['read', 'write'],
        )
        mine = Transaction.objects.create(
            amount=Decimal('10.00'),
            currency='TZS',
            source=TransactionSource.API,
            status=TransactionStatus.CREATED,
            created_by_api_key=self.api_key,
        )
        theirs = Transaction.objects.create(
            amount=Decimal('20.00'),
            currency='TZS',
            source=TransactionSource.API,
            status=TransactionStatus.CREATED,
            created_by_api_key=other_key,
        )
        url = reverse('dev-transaction-list')
        r = self.client.get(url, **self._headers())
        self.assertEqual(r.status_code, 200)
        payload = r.data
        if isinstance(payload, dict) and 'results' in payload:
            rows = payload['results']
        else:
            rows = payload
        ids = {str(row['id']) for row in rows}
        self.assertIn(str(mine.pk), ids)
        self.assertNotIn(str(theirs.pk), ids)

    def test_read_scope_cannot_create_transaction(self):
        k = APIKey.objects.create(
            name='read-only',
            key_hash=hash_api_key('read-only-secret'),
            is_active=True,
            scopes=['read'],
        )
        url = reverse('dev-transaction-list')
        r = self.client.post(
            url,
            {
                'amount': '15.00',
                'currency': 'TZS',
                'description': 'x',
            },
            format='json',
            HTTP_X_API_KEY='read-only-secret',
        )
        self.assertEqual(r.status_code, 403)


class MainTransactionPayAuthorizationTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user(username='buyer', password='pw')
        self.seller = User.objects.create_user(username='seller', password='pw')
        self.stranger = User.objects.create_user(username='stranger', password='pw')
        self.txn = Transaction.objects.create(
            amount=Decimal('50.00'),
            currency='TZS',
            source=TransactionSource.API,
            status=TransactionStatus.CREATED,
            buyer_user=self.buyer,
            seller_user=self.seller,
        )

    @override_settings(DEBUG=True)
    def test_stranger_cannot_pay_transaction(self):
        url = reverse('engine-transaction-pay', kwargs={'pk': self.txn.pk})
        self.client.force_authenticate(user=self.stranger)
        r = self.client.post(url, {}, format='json')
        self.assertEqual(r.status_code, 404)

    @override_settings(DEBUG=True)
    def test_seller_cannot_pay_transaction_buyer_only(self):
        url = reverse('engine-transaction-pay', kwargs={'pk': self.txn.pk})
        self.client.force_authenticate(user=self.seller)
        r = self.client.post(
            url,
            {'payment_method': 'selcom', 'buyer_phone': '255700000000'},
            format='json',
        )
        self.assertEqual(r.status_code, 403)

    @override_settings(DEBUG=True)
    def test_buyer_can_access_pay_route(self):
        url = reverse('engine-transaction-pay', kwargs={'pk': self.txn.pk})
        self.client.force_authenticate(user=self.buyer)
        r = self.client.post(
            url,
            {'payment_method': 'selcom', 'buyer_phone': '255700000000'},
            format='json',
        )
        # Mock Selcom in DEBUG returns success without keys
        self.assertIn(r.status_code, (200, 400, 502))


class DisputeCreateTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user(username='b2', password='pw')
        self.seller = User.objects.create_user(username='s2', password='pw')
        self.txn = Transaction.objects.create(
            amount=Decimal('30.00'),
            currency='TZS',
            source=TransactionSource.API,
            status=TransactionStatus.HOLD,
            buyer_user=self.buyer,
            seller_user=self.seller,
        )

    def test_seller_cannot_open_dispute_via_list_create(self):
        url = reverse('engine-dispute-list')
        self.client.force_authenticate(user=self.seller)
        r = self.client.post(
            url,
            {'transaction': str(self.txn.pk), 'reason': 'x' * 15},
            format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_buyer_can_open_dispute_via_list_create(self):
        url = reverse('engine-dispute-list')
        self.client.force_authenticate(user=self.buyer)
        r = self.client.post(
            url,
            {'transaction': str(self.txn.pk), 'reason': 'damaged item xxxx'},
            format='json',
        )
        self.assertEqual(r.status_code, 201)
