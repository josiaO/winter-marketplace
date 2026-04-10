from __future__ import annotations
import mimetypes
import os
import secrets
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, serializers as drf_serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from core.permissions import IsAdmin
from listings.models import Listing
from marketplace.models import SellerProfile
from marketplace.services import sync_store_from_seller_profile
from sellers import verification_media as verification_media_tokens
from sellers.messages import bilingual_identity_submitted, bilingual_status
from sellers.models import (
    SellerActionLog,
    SellerBusinessVerification,
    SellerIDVerification,
    SellerOnboardingProgress,
    SellerPayoutAccount,
)
from sellers.permissions import IsSeller
from sellers.serializers import (
    AdminBusinessRejectSerializer,
    AdminIdentityApproveSerializer,
    AdminIdentityRejectSerializer,
    AdminReinstateSerializer,
    AdminSuspendSerializer,
    BusinessVerificationSerializer,
    IdentityVerificationSerializer,
    PayoutAddSerializer,
    PayoutVerifySerializer,
    StoreSetupSerializer,
)
from sellers import services as seller_svc
from sellers.tasks import (
    notify_admin_business_verification,
    notify_admin_new_verification,
    send_business_approval_notification,
    send_payout_verification,
    send_seller_rejection_email,
    send_seller_suspension_email,
)


def _seller_profile(request):
    return get_object_or_404(SellerProfile.objects.select_related('user'), user=request.user)

def _iso_z(dt):
    if not dt:
        return None
    return dt.isoformat().replace('+00:00', 'Z')

def _verification_media_absolute_url(request, seller_profile_id: int, kind: str) -> str | None:
    if not request:
        return None
    token = verification_media_tokens.sign_verification_media(seller_profile_id, kind)
    path = reverse('sellers_admin:verification-media', kwargs={'token': token})
    return request.build_absolute_uri(path)


class OnboardingProgressView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        try:
            sp = request.user.seller_profile
        except (AttributeError, SellerProfile.DoesNotExist):
            return Response({
                'steps': {
                    'registration': True,
                    'store_setup': False,
                    'id_submitted': False,
                    'id_approved': False,
                    'payout_added': False,
                    'first_product': False,
                    'business_upgraded': False,
                },
                'completion_percentage': 0,
                'verification_status': 'not_started',
                'store_is_active': False,
                'rejection_reason': None,
                'message_en': 'Please complete store setup to become a seller.',
                'message_sw': 'Tafadhali kamilisha maelezo ya duka ili uwe muuzaji.',
            })

        progress, _ = SellerOnboardingProgress.objects.get_or_create(seller=sp)
        iv = getattr(sp, 'id_verification', None)
        rejection = None
        if sp.verification_status == 'rejected' and iv:
            rejection = iv.rejection_reason or None

        payload = {
            'steps': {
                'registration': progress.step_registration,
                'store_setup': progress.step_store_setup,
                'id_submitted': progress.step_id_submitted,
                'id_approved': progress.step_id_approved,
                'payout_added': progress.step_payout_added,
                'first_product': progress.step_first_product,
                'business_upgraded': progress.step_business_upgraded,
            },
            'completion_percentage': seller_svc.get_onboarding_completion_percentage(progress),
            'verification_status': sp.verification_status,
            'store_is_active': sp.is_active,
            'rejection_reason': rejection,
        }
        payload.update(bilingual_status(sp.verification_status))

        return Response(payload)


class StoreSetupView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    @extend_schema(tags=['sellers'], request=StoreSetupSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        sp = _seller_profile(request)
        ser = StoreSetupSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        sp.store_name = d['store_name'].strip()
        sp.store_categories = list(d['store_categories'])
        sp.store_category_other = (d.get('store_category_other') or '').strip()
        sp.store_location = d['store_location'].strip()
        sp.store_description = (d.get('store_description') or '').strip()
        sp.business_name = sp.store_name
        sp.save()

        # Sync using top-level import
        try:
            sync_store_from_seller_profile(sp)
        except Exception:
            pass

        progress, _ = SellerOnboardingProgress.objects.get_or_create(seller=sp)
        progress.step_store_setup = True
        progress.save(update_fields=['step_store_setup'])

        return Response(
            {
                'id': sp.id,
                'store_name': sp.store_name,
                'store_categories': sp.store_categories,
                'store_category': sp.store_category,
                'store_category_other': sp.store_category_other,
                'store_location': sp.store_location,
                'store_description': sp.store_description,
                'verification_status': sp.verification_status,
                'is_active': sp.is_active,
            }
        )


class IdentityVerificationSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(tags=['sellers'], request=IdentityVerificationSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        sp = _seller_profile(request)
        progress, _ = SellerOnboardingProgress.objects.get_or_create(seller=sp)
        if not progress.step_store_setup:
            return Response(
                {'error': 'Please complete your store setup first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = IdentityVerificationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data

        with transaction.atomic():
            rec, _ = SellerIDVerification.objects.select_for_update().get_or_create(seller=sp)
            rec.id_type = vd['id_type']
            rec.id_number = vd['id_number'].strip()
            rec.id_front_image = vd['id_front_image']
            rec.selfie_with_id = vd['selfie_with_id']
            rec.rejection_reason = ''
            rec.reviewed_at = None
            rec.reviewed_by = None
            rec.save()

            sp.verification_status = 'under_review'
            sp.is_verified = False
            sp.save()

            progress.step_id_submitted = True
            progress.save(update_fields=['step_id_submitted'])

        seller_svc.notify_staff_identity_submission_in_app(sp)
        notify_admin_new_verification.delay(sp.pk)

        rec.refresh_from_db()
        payload = {
            'submitted_at': _iso_z(rec.submitted_at),
            'verification_status': sp.verification_status,
        }
        payload.update(bilingual_identity_submitted())
        return Response(payload)


class IdentityVerificationStatusView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    @extend_schema(tags=['sellers'], responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        sp = _seller_profile(request)
        iv = getattr(sp, 'id_verification', None)
        st = sp.verification_status
        payload = {
            'status': st,
            'submitted_at': _iso_z(iv.submitted_at) if iv else None,
            'reviewed_at': _iso_z(iv.reviewed_at) if iv and iv.reviewed_at else None,
            'rejection_reason': (iv.rejection_reason if iv and st == 'rejected' else None),
        }
        payload.update(bilingual_status(st))
        return Response(payload)


class PayoutAddView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    @extend_schema(tags=['sellers'], request=PayoutAddSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        sp = _seller_profile(request)
        if sp.verification_status != 'verified':
            return Response(
                {
                    'error': (
                        'Your identity must be verified before adding a payout account.'
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        ser = PayoutAddSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data

        code = f'{secrets.randbelow(10**6):06d}'
        acct = SellerPayoutAccount.objects.create(
            seller=sp,
            account_type=vd['account_type'],
            account_number=vd['account_number'].strip(),
            account_name=vd['account_name'].strip(),
            bank_code=vd.get('bank_code', '').strip(),
            verification_code=code,
        )
        send_payout_verification.delay(acct.pk)

        return Response(
            {
                'message': (
                    f'We sent TZS 1 to {acct.account_number}. Check the transaction description for your '
                    '6-digit code and enter it below.'
                ),
                'payout_account_id': acct.pk,
            }
        )


class PayoutVerifyView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    @extend_schema(tags=['sellers'], request=PayoutVerifySerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        sp = _seller_profile(request)
        ser = PayoutVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data
        code = vd['verification_code'].strip()
        acct = get_object_or_404(SellerPayoutAccount, pk=vd['payout_account_id'], seller=sp)

        if acct.verification_code != code:
            return Response(
                {'error': 'Incorrect code. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            SellerPayoutAccount.objects.filter(seller=sp).update(is_primary=False)
            acct.is_verified = True
            acct.is_primary = True
            acct.save(update_fields=['is_verified', 'is_primary'])
            progress, _ = SellerOnboardingProgress.objects.get_or_create(seller=sp)
            progress.step_payout_added = True
            progress.save(update_fields=['step_payout_added'])

        return Response({'message': 'Payout account verified successfully.'})


def _identity_submission_summary(sp: SellerProfile) -> dict | None:
    """Read-only snapshot for seller dashboard (same DB row as marketplace onboarding)."""
    iv = getattr(sp, 'id_verification', None)
    if not iv:
        return None
    return {
        'id_type': iv.id_type,
        'id_number': iv.id_number,
        'submitted_at': _iso_z(iv.submitted_at),
        'seller_verification_status': sp.verification_status,
    }


class SellerProfileDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    @extend_schema(tags=['sellers'], responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        sp = _seller_profile(request)
        progress, _ = SellerOnboardingProgress.objects.get_or_create(seller=sp)
        payouts = [
            {
                'id': p.id,
                'account_type': p.account_type,
                'account_number': p.account_number,
                'account_name': p.account_name,
                'is_primary': p.is_primary,
            }
            for p in sp.payout_accounts.filter(is_verified=True)
        ]
        business_available = (
            sp.total_sales >= Decimal('500000') or sp.completed_orders >= 20
        ) and not progress.step_business_upgraded

        payload = {
            'id': sp.id,
            'store_name': sp.store_name,
            'store_category': sp.store_category,
            'store_categories': sp.store_categories or [],
            'store_category_other': sp.store_category_other or '',
            'store_location': sp.store_location,
            'store_description': sp.store_description,
            'store_logo': sp.store_logo.url if sp.store_logo else None,
            'business_email': sp.business_email or '',
            'business_phone': sp.business_phone or '',
            'business_address': sp.business_address or '',
            'notification_orders': sp.notification_orders,
            'notification_messages': sp.notification_messages,
            'notification_reviews': sp.notification_reviews,
            'notification_marketing': sp.notification_marketing,
            'auto_accept_orders': sp.auto_accept_orders,
            'require_phone_confirmation': sp.require_phone_confirmation,
            'shipping_method': sp.shipping_method,
            'return_policy': sp.return_policy or '',
            'verification_status': sp.verification_status,
            'is_active': sp.is_active,
            'products_limit': sp.products_limit,
            'payout_limit': str(sp.payout_limit),
            'total_sales': str(sp.total_sales),
            'completed_orders': sp.completed_orders,
            'is_business_verified': sp.is_business_verified,
            'business_name': sp.business_name,
            'business_type': sp.business_type,
            'average_rating': sp.average_rating,
            'total_reviews': sp.total_reviews,
            'onboarding': {
                'registration': progress.step_registration,
                'store_setup': progress.step_store_setup,
                'id_submitted': progress.step_id_submitted,
                'id_approved': progress.step_id_approved,
                'payout_added': progress.step_payout_added,
                'first_product': progress.step_first_product,
                'business_upgraded': progress.step_business_upgraded,
            },
            'payout_accounts': payouts,
            'business_upgrade_available': business_available,
            'identity_submission': _identity_submission_summary(sp),
        }
        payload.update(bilingual_status(sp.verification_status))
        return Response(payload)


class BusinessVerificationSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(tags=['sellers'], request=BusinessVerificationSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        sp = _seller_profile(request)
        progress, _ = SellerOnboardingProgress.objects.get_or_create(seller=sp)

        if not (
            sp.total_sales >= Decimal('500000') or sp.completed_orders >= 20
        ):
            return Response(
                {'error': 'Business upgrade is not available yet.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        ser = BusinessVerificationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data

        defaults = {
            'business_name': vd['business_name'].strip(),
            'business_registration_no': (vd.get('business_registration_no') or '').strip(),
            'tin_number': (vd.get('tin_number') or '').strip(),
            'bank_account_number': (vd.get('bank_account_number') or '').strip(),
            'bank_name': (vd.get('bank_name') or '').strip(),
            'bank_account_name': (vd.get('bank_account_name') or '').strip(),
            'status': 'pending',
            'rejection_reason': '',
            'reviewed_at': None,
            'reviewed_by': None,
        }
        obj, _ = SellerBusinessVerification.objects.update_or_create(
            seller=sp,
            defaults=defaults,
        )
        cert = vd.get('business_certificate')
        if cert:
            obj.business_certificate = cert
            obj.save(update_fields=['business_certificate'])

        notify_admin_business_verification.delay(sp.pk)
        return Response({'message': 'Business verification submitted for review.'})


# --- Staff admin API (same module; mounted under /api/admin/sellers/ in root urls) ---


class _AdminQueueListSchemaSerializer(drf_serializers.Serializer):
    """Schema placeholder; AdminVerificationQueueListView.list builds the payload."""

    id = drf_serializers.IntegerField(read_only=True)


class AdminSellerPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


def _seller_admin_queryset():
    return SellerProfile.objects.select_related(
        'user',
        'id_verification',
        'business_verification',
    )


def _log_action(*, seller: SellerProfile, user, action: str, reason: str = '') -> None:
    SellerActionLog.objects.create(
        seller=seller,
        action=action,
        performed_by=user,
        reason=reason or '',
    )


def _serialize_action_log(entry: SellerActionLog) -> dict:
    return {
        'id': entry.pk,
        'action': entry.action,
        'reason': entry.reason,
        'performed_by_id': entry.performed_by_id,
        'performed_by_username': entry.performed_by.get_username(),
        'timestamp': _iso_z(entry.timestamp),
    }


def _serialize_id_verification(
    iv: SellerIDVerification | None,
    request=None,
    seller_profile_id: int | None = None,
) -> dict | None:
    if not iv:
        return None
    sp_id = seller_profile_id if seller_profile_id is not None else iv.seller_id
    front = None
    selfie = None
    if iv.id_front_image:
        front = _verification_media_absolute_url(
            request, sp_id, verification_media_tokens.KIND_ID_FRONT
        )
    if iv.selfie_with_id:
        selfie = _verification_media_absolute_url(
            request, sp_id, verification_media_tokens.KIND_SELFIE
        )
    return {
        'id_type': iv.id_type,
        'id_number': iv.id_number,
        'id_front_image': front,
        'selfie_with_id': selfie,
        'submitted_at': _iso_z(iv.submitted_at),
        'reviewed_at': _iso_z(iv.reviewed_at),
        'reviewed_by_id': iv.reviewed_by_id,
        'rejection_reason': iv.rejection_reason,
        'notes': iv.notes,
    }


def _serialize_business_verification(
    bv: SellerBusinessVerification | None,
    request=None,
    seller_profile_id: int | None = None,
) -> dict | None:
    if not bv:
        return None
    sp_id = seller_profile_id if seller_profile_id is not None else bv.seller_id
    cert = None
    if bv.business_certificate:
        cert = _verification_media_absolute_url(
            request, sp_id, verification_media_tokens.KIND_BUSINESS_CERT
        )
    return {
        'business_name': bv.business_name,
        'business_registration_no': bv.business_registration_no,
        'tin_number': bv.tin_number,
        'business_certificate': cert,
        'bank_account_number': bv.bank_account_number,
        'bank_name': bv.bank_name,
        'bank_account_name': bv.bank_account_name,
        'status': bv.status,
        'submitted_at': _iso_z(bv.submitted_at),
        'reviewed_at': _iso_z(bv.reviewed_at),
        'reviewed_by_id': bv.reviewed_by_id,
        'rejection_reason': bv.rejection_reason,
    }


def _serialize_queue_row(sp: SellerProfile) -> dict:
    iv = getattr(sp, 'id_verification', None)
    bv = getattr(sp, 'business_verification', None)
    flags = []
    if sp.verification_status == 'under_review':
        flags.append('identity')
    if bv and bv.status == 'pending':
        flags.append('business')
    return {
        'id': sp.pk,
        'store_name': sp.store_name,
        'business_name': sp.business_name,
        'verification_status': sp.verification_status,
        'is_active': sp.is_active,
        'is_business_verified': sp.is_business_verified,
        'user': {
            'id': sp.user_id,
            'email': sp.user.email,
            'username': sp.user.get_username(),
        },
        'queue_types': flags,
        'identity_submitted_at': _iso_z(iv.submitted_at) if iv else None,
        'business_submitted_at': _iso_z(bv.submitted_at) if bv else None,
    }


def _serialize_seller_detail(sp: SellerProfile, request=None) -> dict:
    progress, _ = SellerOnboardingProgress.objects.get_or_create(seller=sp)
    iv = getattr(sp, 'id_verification', None)
    bv = getattr(sp, 'business_verification', None)
    logs = [
        _serialize_action_log(x)
        for x in sp.action_logs.order_by('-timestamp')[:50]
    ]
    return {
        'id': sp.pk,
        'store_name': sp.store_name,
        'store_category': sp.store_category,
        'store_categories': sp.store_categories or [],
        'store_category_other': sp.store_category_other or '',
        'store_location': sp.store_location,
        'store_description': sp.store_description,
        'business_name': sp.business_name,
        'business_type': sp.business_type,
        'verification_status': sp.verification_status,
        'is_verified': sp.is_verified,
        'verified_at': _iso_z(sp.verified_at),
        'is_active': sp.is_active,
        'is_business_verified': sp.is_business_verified,
        'products_limit': sp.products_limit,
        'payout_limit': str(sp.payout_limit),
        'total_sales': str(sp.total_sales),
        'completed_orders': sp.completed_orders,
        'suspended_at': _iso_z(sp.suspended_at),
        'suspension_reason': sp.suspension_reason,
        'user': {
            'id': sp.user_id,
            'email': sp.user.email,
            'username': sp.user.get_username(),
        },
        'onboarding': {
            'step_store_setup': progress.step_store_setup,
            'step_id_submitted': progress.step_id_submitted,
            'step_id_approved': progress.step_id_approved,
            'step_payout_added': progress.step_payout_added,
            'step_first_product': progress.step_first_product,
            'step_business_upgraded': progress.step_business_upgraded,
        },
        'identity_verification': _serialize_id_verification(iv, request, sp.pk),
        'business_verification': _serialize_business_verification(bv, request, sp.pk),
        'action_logs': logs,
    }


class AdminVerificationMediaView(APIView):
    """
    Serve ID / business uploads using a time-limited signed token.

    Deliberately AllowAny: URLs are embedded in ``<img src>`` in admin UIs, which cannot
    send ``Authorization``. Only staff can obtain these URLs from the seller detail API.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=['sellers-admin'], responses={200: OpenApiTypes.OBJECT})
    def get(self, request, token):
        try:
            seller_id, kind = verification_media_tokens.parse_verification_media_token(token)
        except (
            verification_media_tokens.BadSignature,
            verification_media_tokens.SignatureExpired,
            ValueError,
        ):
            return Response(
                {'error': 'Invalid or expired link.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        sp = get_object_or_404(SellerProfile.objects.select_related('user'), pk=seller_id)
        field = None
        if kind == verification_media_tokens.KIND_ID_FRONT:
            iv = getattr(sp, 'id_verification', None)
            if iv and iv.id_front_image:
                field = iv.id_front_image
        elif kind == verification_media_tokens.KIND_SELFIE:
            iv = getattr(sp, 'id_verification', None)
            if iv and iv.selfie_with_id:
                field = iv.selfie_with_id
        elif kind == verification_media_tokens.KIND_BUSINESS_CERT:
            bv = getattr(sp, 'business_verification', None)
            if bv and bv.business_certificate:
                field = bv.business_certificate

        if not field:
            return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            fh = field.open('rb')
        except Exception:
            return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)

        name = getattr(field, 'name', '') or ''
        content_type = mimetypes.guess_type(os.path.basename(name))[0] or 'application/octet-stream'
        resp = FileResponse(fh, content_type=content_type)
        resp['Cache-Control'] = 'private, max-age=60'
        return resp


class AdminVerificationQueueListView(generics.ListAPIView):
    """
    Pending identity (under_review) and/or pending business verification rows.
    Query: queue=all|identity|business (default all), plus search & filters.
    """

    serializer_class = _AdminQueueListSchemaSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = AdminSellerPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['verification_status', 'is_business_verified', 'is_active']
    search_fields = (
        'store_name',
        'business_name',
        'user__email',
        'user__username',
        'id_verification__id_number',
    )
    ordering_fields = ('created_at', 'updated_at', 'id_verification__submitted_at')
    ordering = ('-id_verification__submitted_at', '-updated_at')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SellerProfile.objects.none()
        queue = (self.request.query_params.get('queue') or 'all').lower()
        q_identity = Q(verification_status='under_review')
        q_business = Q(business_verification__status='pending')
        base = _seller_admin_queryset()
        if queue == 'identity':
            return base.filter(q_identity).distinct()
        if queue == 'business':
            return base.filter(q_business).distinct()
        return base.filter(q_identity | q_business).distinct()

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        rows = page if page is not None else qs
        data = [_serialize_queue_row(sp) for sp in rows]
        if page is not None:
            return self.get_paginated_response(data)
        return Response(data)


class AdminSellerDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['sellers-admin'], responses={200: OpenApiTypes.OBJECT})
    def get(self, request, pk):
        sp = get_object_or_404(_seller_admin_queryset(), pk=pk)
        return Response(_serialize_seller_detail(sp, request))


class AdminIdentityApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['sellers-admin'], request=AdminIdentityApproveSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, pk):
        ser = AdminIdentityApproveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        notes = (ser.validated_data.get('notes') or '').strip()
        sp = get_object_or_404(SellerProfile.objects.select_related('user'), pk=pk)

        if sp.verification_status == 'suspended':
            return Response(
                {'error': 'Reinstate the seller before changing identity verification.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if sp.verification_status != 'under_review':
            return Response(
                {'error': 'Identity is not awaiting review.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        iv = getattr(sp, 'id_verification', None)
        if not iv:
            return Response(
                {'error': 'No identity documents on file.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            sp_locked = SellerProfile.objects.select_for_update().get(pk=sp.pk)
            seller_svc.approve_seller_identity(sp_locked, request.user, notes)
            
            _log_action(
                seller=sp_locked,
                user=request.user,
                action='approve',
                reason=notes,
            )

        sp_locked.refresh_from_db()
        return Response(_serialize_seller_detail(sp_locked, request))


class AdminIdentityRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['sellers-admin'], request=AdminIdentityRejectSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, pk):
        ser = AdminIdentityRejectSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        reason = ser.validated_data['rejection_reason'].strip()
        sp = get_object_or_404(SellerProfile.objects.select_related('user'), pk=pk)

        if sp.verification_status == 'suspended':
            return Response(
                {'error': 'Cannot reject identity while the seller is suspended.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if sp.verification_status != 'under_review':
            return Response(
                {'error': 'Identity is not awaiting review.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        iv = getattr(sp, 'id_verification', None)
        if not iv:
            return Response(
                {'error': 'No identity documents on file.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            sp_locked = SellerProfile.objects.select_for_update().get(pk=sp.pk)
            seller_svc.reject_seller_identity(sp_locked, request.user, reason)
            
            _log_action(
                seller=sp_locked,
                user=request.user,
                action='reject',
                reason=reason,
            )
            progress, _ = SellerOnboardingProgress.objects.select_for_update().get_or_create(
                seller=sp_locked
            )
            progress.step_id_approved = False
            progress.save(update_fields=['step_id_approved'])
            _log_action(seller=sp_locked, user=request.user, action='reject', reason=reason)

        send_seller_rejection_email.delay(sp_locked.pk, reason)
        sp_locked.refresh_from_db()
        return Response(_serialize_seller_detail(sp_locked, request))


class AdminSellerSuspendView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['sellers-admin'], request=AdminSuspendSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, pk):
        ser = AdminSuspendSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        reason = ser.validated_data['reason'].strip()
        sp = get_object_or_404(SellerProfile.objects.select_related('user'), pk=pk)

        if sp.verification_status == 'suspended':
            return Response({'error': 'Seller is already suspended.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            sp_locked = SellerProfile.objects.select_for_update().get(pk=sp.pk)
            seller_svc.suspend_seller(sp_locked, request.user, reason)
            
            _log_action(
                seller=sp_locked,
                user=request.user,
                action='suspend',
                reason=reason,
            )

        send_seller_suspension_email.delay(sp.pk, reason)
        sp_locked.refresh_from_db()
        return Response(_serialize_seller_detail(sp_locked, request))


class AdminSellerReinstateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['sellers-admin'], request=AdminReinstateSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, pk):
        ser = AdminReinstateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        note = (ser.validated_data.get('reason') or '').strip()
        sp = get_object_or_404(SellerProfile.objects.select_related('user'), pk=pk)

        if sp.verification_status != 'suspended':
            return Response(
                {'error': 'Seller is not suspended.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            sp_locked = SellerProfile.objects.select_for_update().get(pk=sp.pk)
            seller_svc.reinstate_seller(sp_locked, request.user, note)
            
            _log_action(
                seller=sp_locked, 
                user=request.user, 
                action='reinstate', 
                reason=note
            )

        sp_locked.refresh_from_db()
        return Response(_serialize_seller_detail(sp_locked, request))


class AdminBusinessApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['sellers-admin'], request=None, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, pk):
        sp = get_object_or_404(SellerProfile.objects.select_related('user'), pk=pk)

        if sp.verification_status == 'suspended':
            return Response(
                {'error': 'Cannot approve business verification while suspended.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bv = getattr(sp, 'business_verification', None)
        if not bv or bv.status != 'pending':
            return Response(
                {'error': 'No pending business verification.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            sp_locked = SellerProfile.objects.select_for_update().get(pk=sp.pk)
            seller_svc.approve_seller_business(sp_locked, request.user)
            
            _log_action(
                seller=sp_locked,
                user=request.user,
                action='business_approve',
                reason='',
            )

        send_business_approval_notification.delay(sp_locked.pk)
        sp_locked.refresh_from_db()
        return Response(_serialize_seller_detail(sp_locked, request))


class AdminBusinessRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['sellers-admin'], request=AdminBusinessRejectSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request, pk):
        ser = AdminBusinessRejectSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        reason = ser.validated_data['rejection_reason'].strip()
        sp = get_object_or_404(SellerProfile.objects.select_related('user'), pk=pk)

        if sp.verification_status == 'suspended':
            return Response(
                {'error': 'Cannot reject business verification while suspended.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bv = getattr(sp, 'business_verification', None)
        if not bv or bv.status != 'pending':
            return Response(
                {'error': 'No pending business verification.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            sp_locked = SellerProfile.objects.select_for_update().get(pk=sp.pk)
            seller_svc.reject_seller_business(sp_locked, request.user, reason)
            
            _log_action(
                seller=sp_locked,
                user=request.user,
                action='business_reject',
                reason=reason,
            )

        send_seller_rejection_email.delay(sp_locked.pk, f'Business verification: {reason}')
        sp_locked.refresh_from_db()
        return Response(_serialize_seller_detail(sp_locked, request))
