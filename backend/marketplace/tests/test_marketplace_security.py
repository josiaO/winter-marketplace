"""Marketplace boundaries, privacy, checkout path, uploads, slugs."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from commerce.models import Cart, CartItem
from commerce.services.checkout import OrderService
from marketplace.models import MarketplaceItem, SellerProfile, Store
from marketplace.services.store_service import unique_store_slug
from catalog.models import Category

User = get_user_model()


class SellerProfilePrivacyTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.owner = User.objects.create_user(username='sp_owner', password='pw')
        self.stranger = User.objects.create_user(username='sp_stranger', password='pw')
        self.profile = SellerProfile.objects.create(
            user=self.owner,
            business_name='Secret Co',
            tax_id='TAX-SECRET',
            verification_status='verified',
            store_name='Shop',
        )

    def test_stranger_does_not_see_tax_id_in_seller_profile(self):
        client = APIClient()
        client.force_authenticate(self.stranger)
        r = client.get(f'/api/v1/marketplace/sellers/{self.profile.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('tax_id', r.data)
        self.assertNotIn('verification_documents', r.data)
        self.assertNotIn('business_email', r.data)
        self.assertNotIn('business_phone', r.data)
        self.assertNotIn('business_address', r.data)

    def test_anonymous_list_only_verified_active_sellers(self):
        u = User.objects.create_user(username='hid', password='pw')
        hidden = SellerProfile.objects.create(
            user=u,
            verification_status='under_review',
            business_name='Hidden',
            store_name='H',
        )
        client = APIClient()
        r = client.get('/api/v1/marketplace/sellers/')
        self.assertEqual(r.status_code, 200)
        payload = r.data
        rows = payload['results'] if isinstance(payload, dict) and 'results' in payload else payload
        ids = {row['id'] for row in rows}
        self.assertNotIn(hidden.pk, ids)
        self.assertIn(self.profile.pk, ids)

    def test_owner_sees_sensitive_fields(self):
        self.profile.verification_documents = ['https://x/doc.pdf']
        self.profile.save()
        client = APIClient()
        client.force_authenticate(self.owner)
        r = client.get(f'/api/v1/marketplace/sellers/{self.profile.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('tax_id', r.data)
        self.assertIn('verification_documents', r.data)


class VerificationFlowTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.user = User.objects.create_user(username='ver_u', password='pw')
        self.profile = SellerProfile.objects.create(user=self.user, verification_status='incomplete')

    def test_document_upload_moves_to_under_review(self):
        from marketplace.services.seller_service import SellerService

        f = SimpleUploadedFile('id.pdf', b'%PDF-1.4 minimal', content_type='application/pdf')
        SellerService.apply_after_document_upload(self.profile, [f])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.verification_status, 'under_review')

    def test_admin_verify_sets_verified_and_active(self):
        from marketplace.services.seller_service import SellerService

        SellerService.verify_by_admin(self.profile)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.verification_status, 'verified')
        self.assertTrue(self.profile.is_verified)
        self.assertTrue(self.profile.is_active)


class OrderCreationPathTests(TestCase):
    databases = {'default'}

    @patch('django.db.transaction.on_commit', side_effect=lambda f: f())
    @patch('commerce.tasks.send_order_confirmation_email.delay')
    @patch('commerce.tasks.auto_cancel_unpaid_order.apply_async')
    @patch('core.events.emit_event')
    @patch('escrow_engine.services.create_transaction')
    def test_create_order_from_cart_lives_in_commerce(
        self, mock_txn, mock_emit, mock_apply_async, mock_mail_delay, _on_commit
    ):
        buyer = User.objects.create_user(username='buy', password='pw')
        seller = User.objects.create_user(username='sel', password='pw')
        SellerProfile.objects.create(user=seller, verification_status='verified', store_name='S')
        cat = Category.objects.create(name='C', slug='c-slug', vertical='electronics')
        item = MarketplaceItem.objects.create(
            owner=seller,
            category=cat,
            title='Item',
            price=Decimal('10.00'),
            stock_quantity=5,
            track_inventory=True,
            is_published=True,
            status='active',
        )

        cart = Cart.objects.create(user=buyer)
        CartItem.objects.create(cart=cart, listing=item, quantity=1, price_at_time=item.price)

        mock_txn.return_value = MagicMock(reference='TX-REF')

        order = OrderService.create_order_from_cart(cart, 'Addr', payment_method='mpesa')
        self.assertEqual(order.buyer_id, buyer.id)
        self.assertEqual(order.seller_id, seller.id)
        mock_txn.assert_called_once()


class DocumentUploadValidationTests(TestCase):
    databases = {'default'}

    def setUp(self):
        self.user = User.objects.create_user(username='du', password='pw')
        self.profile = SellerProfile.objects.create(user=self.user)

    def test_rejects_oversize_and_bad_extension(self):
        from marketplace.services.seller_service import SellerService

        big = SimpleUploadedFile('x.pdf', b'x' * (6 * 1024 * 1024), content_type='application/pdf')
        with self.assertRaises(ValueError):
            SellerService.apply_after_document_upload(self.profile, [big])

        exe = SimpleUploadedFile('x.exe', b'MZ', content_type='application/octet-stream')
        with self.assertRaises(ValueError):
            SellerService.apply_after_document_upload(self.profile, [exe])

    def test_rejects_mime_extension_mismatch(self):
        from marketplace.services.seller_service import SellerService

        bad = SimpleUploadedFile('x.png', b'\x89PNG\r\n\x1a\n', content_type='application/pdf')
        with self.assertRaises(ValueError):
            SellerService.apply_after_document_upload(self.profile, [bad])


class StoreSlugUniquenessTests(TestCase):
    databases = {'default'}

    def test_unique_store_slug_no_collision(self):
        user = User.objects.create_user(username='slug_u', password='pw')
        sp = SellerProfile.objects.create(user=user, verification_status='verified', store_name='Z')
        s1 = Store.objects.create(seller=sp, name='A', slug=unique_store_slug('my-store'), is_active=True)
        s2_slug = unique_store_slug('my-store')
        self.assertNotEqual(s1.slug, s2_slug)
        Store.objects.create(seller=sp, name='B', slug=s2_slug, is_active=True)
