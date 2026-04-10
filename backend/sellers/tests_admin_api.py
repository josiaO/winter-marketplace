"""Tests for staff admin seller governance API."""
from decimal import Decimal
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from listings.models import Listing
from marketplace.models import SellerProfile
from sellers.models import (
    SellerActionLog,
    SellerBusinessVerification,
    SellerIDVerification,
    SellerOnboardingProgress,
)

User = get_user_model()


def _img(name='x.jpg'):
    return SimpleUploadedFile(name, b'\xff\xd8\xff', content_type='image/jpeg')


class AdminSellerGovernanceAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='admin_gov',
            email='a@example.com',
            password='x',
            is_staff=True,
        )
        self.user = User.objects.create_user(
            username='seller_u',
            email='s@example.com',
            password='x',
        )
        self.sp = SellerProfile.objects.create(
            user=self.user,
            store_name='Test Store',
            verification_status='under_review',
        )
        SellerOnboardingProgress.objects.get_or_create(seller=self.sp)
        SellerIDVerification.objects.create(
            seller=self.sp,
            id_type='national_id',
            id_number='ABC123',
            id_front_image=_img('front.jpg'),
            selfie_with_id=_img('selfie.jpg'),
        )

    def test_queue_forbidden_non_staff(self):
        self.client.force_authenticate(self.user)
        url = reverse('sellers_admin:verification-queue')
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_queue_lists_identity_pending(self):
        self.client.force_authenticate(self.admin)
        url = reverse('sellers_admin:verification-queue')
        r = self.client.get(url, {'queue': 'identity'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['id'], self.sp.pk)

    @patch('sellers.signals.send_seller_approval_email.delay')
    @patch('core.services.notifications.PushNotificationService')
    def test_identity_approve(self, mock_ps, _email):
        mock_ps.return_value.send_push = MagicMock()
        self.client.force_authenticate(self.admin)
        url = reverse('sellers_admin:identity-approve', kwargs={'pk': self.sp.pk})
        r = self.client.post(url, {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.verification_status, 'verified')
        self.assertTrue(self.sp.is_active)
        self.assertTrue(
            SellerActionLog.objects.filter(seller=self.sp, action='approve').exists()
        )

    def test_verification_media_anonymous_with_valid_token(self):
        self.client.force_authenticate(self.admin)
        detail = reverse('sellers_admin:seller-detail', kwargs={'pk': self.sp.pk})
        r = self.client.get(detail)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        url = r.data['identity_verification']['id_front_image']
        self.assertIsNotNone(url)
        path = urlparse(url).path
        self.client.force_authenticate(user=None)
        r2 = self.client.get(path)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)

    def test_verification_media_invalid_token(self):
        self.client.force_authenticate(user=None)
        url = reverse('sellers_admin:verification-media', kwargs={'token': 'invalid'})
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    @patch('sellers.views.send_seller_rejection_email.delay')
    def test_identity_reject(self, mock_rej):
        self.client.force_authenticate(self.admin)
        url = reverse('sellers_admin:identity-reject', kwargs={'pk': self.sp.pk})
        r = self.client.post(
            url, {'rejection_reason': 'Blurry photo'}, format='json'
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.verification_status, 'rejected')
        mock_rej.assert_called_once()
        self.assertTrue(
            SellerActionLog.objects.filter(seller=self.sp, action='reject').exists()
        )

    @patch('sellers.views.send_seller_suspension_email.delay')
    def test_suspend_reinstate_verified_seller(self, _susp):
        self.sp.verification_status = 'verified'
        self.sp.is_verified = True
        self.sp.is_active = True
        self.sp.save()
        p = self.sp.onboarding_progress
        p.step_id_approved = True
        p.save()
        self.client.force_authenticate(self.admin)
        sus = reverse('sellers_admin:seller-suspend', kwargs={'pk': self.sp.pk})
        r = self.client.post(sus, {'reason': 'Fraud'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.verification_status, 'suspended')
        self.assertFalse(self.sp.is_active)
        rst = reverse('sellers_admin:seller-reinstate', kwargs={'pk': self.sp.pk})
        r2 = self.client.post(rst, {}, format='json')
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.verification_status, 'verified')
        self.assertTrue(self.sp.is_active)

    @patch('sellers.views.send_seller_suspension_email.delay')
    def test_suspend_unpublishes_listings(self, _susp):
        self.sp.verification_status = 'verified'
        self.sp.is_verified = True
        self.sp.is_active = True
        self.sp.save()
        lst = Listing.objects.create(
            owner=self.user,
            title='Test product',
            price=Decimal('10.00'),
            is_published=True,
        )
        self.client.force_authenticate(self.admin)
        sus = reverse('sellers_admin:seller-suspend', kwargs={'pk': self.sp.pk})
        r = self.client.post(sus, {'reason': 'Policy'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        lst.refresh_from_db()
        self.assertFalse(lst.is_published)

    @patch('sellers.views.send_business_approval_notification.delay')
    @patch('core.services.notifications.PushNotificationService')
    def test_business_approve(self, mock_ps, _biz):
        mock_ps.return_value.send_push = MagicMock()
        self.sp.verification_status = 'verified'
        self.sp.is_verified = True
        self.sp.is_active = True
        self.sp.total_sales = Decimal('500000')
        self.sp.save()
        SellerBusinessVerification.objects.create(
            seller=self.sp,
            business_name='Biz Co',
            status='pending',
        )
        self.client.force_authenticate(self.admin)
        url = reverse('sellers_admin:business-approve', kwargs={'pk': self.sp.pk})
        r = self.client.post(url, {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.sp.refresh_from_db()
        self.assertTrue(self.sp.is_business_verified)
        self.assertEqual(self.sp.products_limit, 500)
        self.assertEqual(self.sp.payout_limit, Decimal('0'))
        self.assertTrue(
            SellerActionLog.objects.filter(
                seller=self.sp, action='business_approve'
            ).exists()
        )

    @patch('sellers.views.send_seller_rejection_email.delay')
    def test_business_reject(self, _rej):
        self.sp.verification_status = 'verified'
        self.sp.is_verified = True
        self.sp.save()
        SellerBusinessVerification.objects.create(
            seller=self.sp,
            business_name='Biz Co',
            status='pending',
        )
        self.client.force_authenticate(self.admin)
        url = reverse('sellers_admin:business-reject', kwargs={'pk': self.sp.pk})
        r = self.client.post(
            url, {'rejection_reason': 'Invalid certificate'}, format='json'
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(
            SellerActionLog.objects.filter(
                seller=self.sp, action='business_reject'
            ).exists()
        )
