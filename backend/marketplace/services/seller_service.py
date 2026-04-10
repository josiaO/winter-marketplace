"""
Seller verification state machine, documents, reviews, follows.

Rules (enforced here + SellerProfile.save):
- verification_status == verified → is_verified True, is_active True
- any other status → is_verified False, is_active False
"""
from __future__ import annotations

import logging
import mimetypes
import os
import re
from typing import TYPE_CHECKING

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.crypto import get_random_string as random_token

from marketplace.models import SellerProfile, Store, StoreFollow
from trust.models import Review

from core.logging_context import log_extra

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

logger = logging.getLogger(__name__)

ALLOWED_DOC_EXTENSIONS = frozenset({'.pdf', '.jpg', '.jpeg', '.png'})
MAX_DOC_BYTES = 5 * 1024 * 1024

EXT_ALLOWED_MIMES: dict[str, frozenset[str]] = {
    '.pdf': frozenset({'application/pdf'}),
    '.jpg': frozenset({'image/jpeg'}),
    '.jpeg': frozenset({'image/jpeg'}),
    '.png': frozenset({'image/png', 'image/x-png'}),
}

PENDING_LIKE = frozenset({'incomplete', 'pending_id'})

# Canonical lifecycle (DB may still use legacy labels; map via _normalized in API)
SELLER_LIFECYCLE_PENDING = frozenset({'incomplete', 'pending_id'})
SELLER_LIFECYCLE_UNDER_REVIEW = frozenset({'under_review'})
SELLER_LIFECYCLE_VERIFIED = frozenset({'verified'})
SELLER_LIFECYCLE_SUSPENDED = frozenset({'suspended'})


def _secure_filename(name: str) -> str:
    base = os.path.basename(name or '')
    base = re.sub(r'[^a-zA-Z0-9._-]', '_', base)
    return (base or 'document')[:180]


def _validate_upload_file(f: UploadedFile, *, seller_id: int | None = None) -> None:
    if f.size > MAX_DOC_BYTES:
        logger.warning(
            'seller_document_upload_rejected',
            extra=log_extra(
                reason='file_too_large',
                seller_id=seller_id,
                declared_size=getattr(f, 'size', None),
                max_bytes=MAX_DOC_BYTES,
                filename=(f.name or '')[:200],
            ),
        )
        raise ValueError(f'File too large (max {MAX_DOC_BYTES // (1024 * 1024)} MB).')
    ext = os.path.splitext(f.name or '')[1].lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        logger.warning(
            'seller_document_upload_rejected',
            extra=log_extra(
                reason='bad_extension',
                seller_id=seller_id,
                extension=ext,
                filename=(f.name or '')[:200],
            ),
        )
        raise ValueError(f'Unsupported file type "{ext}". Allowed: {", ".join(sorted(ALLOWED_DOC_EXTENSIONS))}.')

    declared = (getattr(f, 'content_type', '') or '').split(';')[0].strip().lower()
    allowed_mimes = EXT_ALLOWED_MIMES.get(ext, frozenset())
    if declared and allowed_mimes and declared not in allowed_mimes:
        logger.warning(
            'seller_document_upload_rejected',
            extra=log_extra(
                reason='mime_mismatch',
                seller_id=seller_id,
                extension=ext,
                content_type=declared,
                filename=(f.name or '')[:200],
            ),
        )
        raise ValueError('File content type does not match allowed type for this extension.')

    sniff, _ = mimetypes.guess_type(f.name or '')
    if sniff:
        sniff_l = sniff.lower()
        if allowed_mimes and sniff_l not in allowed_mimes:
            logger.warning(
                'seller_document_upload_rejected',
                extra=log_extra(
                    reason='filename_mime_sniff_mismatch',
                    seller_id=seller_id,
                    guessed_mime=sniff_l,
                    extension=ext,
                ),
            )
            raise ValueError('File type does not match extension.')


def handle_seller_document_upload(seller: SellerProfile, files: list) -> list[str]:
    document_urls = list(seller.verification_documents or [])
    uploaded_urls: list[str] = []

    for file in files:
        _validate_upload_file(file, seller_id=seller.id)
        safe_name = _secure_filename(getattr(file, 'name', 'doc'))
        rel_path = f'seller_verification/{seller.id}/{random_token(10)}-{safe_name}'
        saved_path = default_storage.save(rel_path, ContentFile(file.read()))
        uploaded_urls.append(default_storage.url(saved_path))

    seller.verification_documents = document_urls + uploaded_urls
    seller.save(update_fields=['verification_documents', 'updated_at'])
    return uploaded_urls


def get_seller_review_stats(seller_profile: SellerProfile, user=None):
    seller = seller_profile.user

    base_filter = Q(seller=seller, is_approved=True, is_hidden=False)
    if user and user.is_authenticated:
        base_filter |= Q(seller=seller, buyer=user)

    queryset = Review.objects.filter(base_filter)

    rating_distribution = queryset.values('rating').annotate(count=Count('id')).order_by('-rating')
    distribution_dict = {r['rating']: r['count'] for r in rating_distribution}

    return {
        'average_rating': seller_profile.average_rating,
        'total_reviews': seller_profile.total_reviews,
        'rating_distribution': distribution_dict,
        'queryset': queryset.select_related('buyer', 'listing', 'order').order_by('-created_at'),
    }


@transaction.atomic
def toggle_store_follow(user, store: Store, follow: bool = True) -> int:
    if follow:
        StoreFollow.objects.get_or_create(user=user, store=store)
    else:
        StoreFollow.objects.filter(user=user, store=store).delete()

    store.total_followers = StoreFollow.objects.filter(store=store).count()
    store.save(update_fields=['total_followers', 'updated_at'])
    return store.total_followers


class SellerService:
    """Seller profile + verification state machine (single owner of transitions)."""

    @staticmethod
    def refresh_flags_from_verification_status(seller: SellerProfile) -> None:
        """Re-apply is_verified/is_active from verification_status (admin repair only)."""
        SellerService.sync_verification_derivatives(seller)
        seller.save(update_fields=['is_verified', 'is_active', 'updated_at'])

    @staticmethod
    def sync_verification_derivatives(seller: SellerProfile) -> None:
        if seller.verification_status == 'verified':
            seller.is_verified = True
            seller.is_active = True
        else:
            seller.is_verified = False
            seller.is_active = False

    @staticmethod
    @transaction.atomic
    def apply_after_document_upload(seller: SellerProfile, files: list) -> list[str]:
        urls = handle_seller_document_upload(seller, files)
        seller.refresh_from_db()
        if seller.verification_status in PENDING_LIKE | {'rejected'}:
            seller.verification_status = 'under_review'
            SellerService.sync_verification_derivatives(seller)
            seller.save(
                update_fields=['verification_status', 'is_verified', 'is_active', 'updated_at'],
            )
        from marketplace.services.store_service import sync_store_from_seller_profile

        sync_store_from_seller_profile(seller)
        return urls

    @staticmethod
    @transaction.atomic
    def verify_by_admin(seller: SellerProfile) -> SellerProfile:
        seller.verification_status = 'verified'
        seller.verified_at = timezone.now()
        seller.suspended_at = None
        seller.suspension_reason = ''
        SellerService.sync_verification_derivatives(seller)
        seller.save(
            update_fields=[
                'verification_status',
                'verified_at',
                'suspended_at',
                'suspension_reason',
                'is_verified',
                'is_active',
                'updated_at',
            ],
        )
        from marketplace.services.store_service import sync_store_from_seller_profile

        sync_store_from_seller_profile(seller)
        return seller

    @staticmethod
    @transaction.atomic
    def unverify_by_admin(seller: SellerProfile) -> SellerProfile:
        seller.verification_status = 'incomplete'
        seller.verified_at = None
        SellerService.sync_verification_derivatives(seller)
        seller.save(
            update_fields=[
                'verification_status',
                'verified_at',
                'is_verified',
                'is_active',
                'updated_at',
            ],
        )
        from marketplace.services.store_service import sync_store_from_seller_profile

        sync_store_from_seller_profile(seller)
        return seller

    @staticmethod
    @transaction.atomic
    def suspend_by_admin(seller: SellerProfile, reason: str = '') -> SellerProfile:
        seller.verification_status = 'suspended'
        seller.suspended_at = timezone.now()
        seller.suspension_reason = (reason or '')[:2000]
        SellerService.sync_verification_derivatives(seller)
        seller.save(
            update_fields=[
                'verification_status',
                'suspended_at',
                'suspension_reason',
                'is_verified',
                'is_active',
                'updated_at',
            ],
        )
        from marketplace.services.store_service import sync_store_from_seller_profile

        sync_store_from_seller_profile(seller)
        return seller

    @staticmethod
    @transaction.atomic
    def reopen_after_suspension(seller: SellerProfile) -> SellerProfile:
        """Admin: move suspended seller back into review (not publicly verified)."""
        seller.verification_status = 'under_review'
        seller.suspended_at = None
        seller.suspension_reason = ''
        SellerService.sync_verification_derivatives(seller)
        seller.save(
            update_fields=[
                'verification_status',
                'suspended_at',
                'suspension_reason',
                'is_verified',
                'is_active',
                'updated_at',
            ],
        )
        from marketplace.services.store_service import sync_store_from_seller_profile

        sync_store_from_seller_profile(seller)
        return seller

    @staticmethod
    @transaction.atomic
    def reject_verification(seller: SellerProfile, notes: str = '') -> SellerProfile:
        seller.verification_status = 'rejected'
        seller.verified_at = None
        SellerService.sync_verification_derivatives(seller)
        if notes:
            seller.suspension_reason = notes[:2000]
        seller.save(
            update_fields=[
                'verification_status',
                'verified_at',
                'suspension_reason',
                'is_verified',
                'is_active',
                'updated_at',
            ],
        )
        from marketplace.services.store_service import sync_store_from_seller_profile

        sync_store_from_seller_profile(seller)
        return seller

    @staticmethod
    def get_or_create_seller_profile(user):
        profile, _ = SellerProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def update_seller_ratings(seller_profile: SellerProfile):
        from trust.services import update_seller_rating

        return update_seller_rating(seller_profile.user)
