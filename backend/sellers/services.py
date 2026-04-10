"""
Synchronous seller automation: email, in-app/push notifications, payout integrations.

Celery tasks in ``sellers.tasks`` should stay thin and call into this module so
SMTP/Selcom/push logic lives in one place and is easy to test or swap.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from listings.models import Listing
from marketplace.models import SellerProfile
from core.services.notifications import BaseNotificationService, PushNotificationService
from .models import (
    SellerOnboardingProgress, SellerIDVerification, 
    SellerBusinessVerification, SellerPayoutAccount
)

logger = logging.getLogger(__name__)


def seller_dashboard_link() -> str:
    base = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
    return f'{base}/seller/dashboard'


def _outbound_email_from():
    return settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER


def staff_notification_emails() -> list[str]:
    User = get_user_model()
    return list(
        User.objects.filter(is_staff=True)
        .exclude(email='')
        .values_list('email', flat=True)
        .distinct()
    )


def notify_staff_identity_submission_in_app(seller_profile) -> None:
    """Create in-app / DB notifications for staff when a seller submits ID docs."""
    title = 'New seller verification'
    body = (
        f'New seller verification request from '
        f'{seller_profile.store_name or seller_profile.business_name or seller_profile.user.email}'
    )
    User = get_user_model()
    svc = BaseNotificationService()
    for u in User.objects.filter(is_staff=True):
        try:
            svc.create_db_notification(
                u,
                'seller_verification',
                title,
                body,
                data={'seller_id': seller_profile.pk},
            )
        except Exception:
            logger.debug('notify_staff_identity_submission_in_app: skip user_id=%s', u.pk, exc_info=True)


def send_seller_approval_email_sync(seller_profile) -> None:
    """Notify seller that identity verification was approved. Raises on mail failure."""
    user = seller_profile.user
    if not user.email:
        return
    subject = 'Your store is now live!'
    body = (
        f"Hello {user.get_full_name() or user.username},\n\n"
        f'Your store "{seller_profile.store_name or seller_profile.business_name or "your store"}" '
        f'is approved and live.\n'
        f'Open your seller dashboard: {seller_dashboard_link()}\n'
    )
    send_mail(
        subject,
        body,
        _outbound_email_from(),
        [user.email],
        fail_silently=False,
    )


def send_seller_rejection_email_sync(seller_profile, rejection_reason: str) -> None:
    """Notify seller that verification was rejected (email if available; push when possible)."""
    user = seller_profile.user
    if user.email:
        subject = 'Action needed: verification update'
        body = (
            f"Hello {user.get_full_name() or user.username},\n\n"
            f'We could not approve your documents yet.\n\n'
            f'Reason:\n{rejection_reason}\n\n'
            f'Please update and resubmit from your dashboard.\n{seller_dashboard_link()}\n'
        )
        send_mail(
            subject,
            body,
            _outbound_email_from(),
            [user.email],
            fail_silently=False,
        )
    reason_stripped = (rejection_reason or '').strip()
    is_business = reason_stripped.startswith('Business verification:')
    if is_business:
        push_title = 'Uthibitisho wa biashara umekataliwa'
        push_body = (
            'Maombi yako ya biashara hayajaidhinishwa. Angalia programu au barua pepe kwa maelezo.'
        )
        data_type = 'seller_business_rejected'
    else:
        push_title = 'Utambulisho haukuidhinishwa'
        push_body = (
            'Nyaraka zako hazikuidhinishwa. Fungua programu kuona sababu na urekebishe.'
        )
        data_type = 'seller_identity_rejected'
    try:
        PushNotificationService().send_push(
            user,
            push_title,
            push_body,
            data={'type': data_type, 'seller_id': str(seller_profile.pk)},
        )
    except Exception:
        logger.debug('send_seller_rejection_email_sync: push skipped', exc_info=True)


def send_seller_suspension_email_sync(seller_profile, reason: str) -> None:
    """Notify seller of suspension. Raises on mail failure."""
    user = seller_profile.user
    if not user.email:
        return
    subject = 'Your seller account has been suspended'
    body = (
        f"Hello {user.get_full_name() or user.username},\n\n"
        f'Your seller account has been suspended.\n\n'
        f'Reason:\n{reason}\n\n'
        f'If you believe this is a mistake, contact support.\n'
    )
    send_mail(
        subject,
        body,
        _outbound_email_from(),
        [user.email],
        fail_silently=False,
    )


def notify_staff_new_identity_verification_sync(seller_profile) -> None:
    """Email staff that a seller submitted ID documents. Raises on mail failure."""
    store = (
        seller_profile.store_name
        or seller_profile.business_name
        or seller_profile.user.email
    )
    subject = f'New seller verification: {store}'
    body = (
        f'A seller submitted identity documents for review.\n'
        f'Seller profile ID: {seller_profile.pk}\nStore: {store}\n'
    )
    emails = staff_notification_emails()
    if not emails:
        logger.warning('notify_staff_new_identity_verification: no staff emails')
        return
    send_mail(
        subject,
        body,
        _outbound_email_from(),
        emails,
        fail_silently=False,
    )


def notify_staff_business_verification_sync(seller_profile) -> None:
    """Email staff that business verification was submitted. Raises on mail failure."""
    subject = f'Business verification submitted: {seller_profile.store_name or seller_profile.business_name}'
    body = f'Seller profile ID {seller_profile.pk} submitted business verification for review.\n'
    emails = staff_notification_emails()
    if not emails:
        return
    send_mail(
        subject,
        body,
        _outbound_email_from(),
        emails,
        fail_silently=False,
    )


def run_payout_verification_disbursement(payout_account) -> None:
    """
    Trigger payout-account verification (micro-deposit with reference code).

    Production: integrate Selcom (or bank) API to send TZS 1 with ``verification_code``
    in the transaction narrative. This implementation only logs in development.
    """
    code = payout_account.verification_code
    
    # Simulation: Print code to console for development
    from django.conf import settings
    import os
    if not os.getenv('SELCOM_API_KEY'):
        print("\n" + "="*80)
        print(" [PAYOUT VERIFICATION CODE] ".center(80, "="))
        print(f" ACCOUNT: {payout_account.account_number} ({payout_account.account_type})".center(80))
        print(f" CODE: {code}".center(80))
        print("="*80 + "\n")

    logger.info(
        '[PAYOUT_VERIFICATION] account=%s type=%s code=%s (Selcom integration pending)',
        payout_account.account_number,
        payout_account.account_type,
        code,
    )


def try_send_business_upgrade_prompt(seller_id: int) -> bool:
    """
    If the seller is eligible and the prompt was not sent yet, mark sent and
    deliver push + email. Returns True if a prompt was delivered.
    """
    # Resolve profile first so we never mark upgrade_prompt_sent when the row is gone
    # (stale Celery tasks, deleted seller, or worker DB drift).
    try:
        sp = SellerProfile.objects.select_related('user').get(pk=seller_id)
    except SellerProfile.DoesNotExist:
        logger.warning(
            'try_send_business_upgrade_prompt: SellerProfile pk=%s missing; skipping (stale task or deleted seller)',
            seller_id,
        )
        return False

    try:
        with transaction.atomic():
            progress, _ = SellerOnboardingProgress.objects.select_for_update().get_or_create(
                seller=sp,
            )
            n = SellerOnboardingProgress.objects.filter(
                pk=progress.pk,
                upgrade_prompt_sent=False,
                step_business_upgraded=False,
            ).update(upgrade_prompt_sent=True)
            if not n:
                return False
    except Exception:
        logger.exception('try_send_business_upgrade_prompt: atomic update failed seller_id=%s', seller_id)
        return False

    user = sp.user
    PushNotificationService().send_push(
        user,
        'Business account upgrade',
        'You qualify to upgrade your seller account and remove limits.',
        data={'type': 'seller_business_upgrade', 'seller_id': str(sp.pk)},
    )
    if user.email:
        try:
            send_mail(
                'You qualify for a business account upgrade',
                f'Upgrade your SmartDalali seller account to unlock higher limits.\n{seller_dashboard_link()}\n',
                _outbound_email_from(),
                [user.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception('try_send_business_upgrade_prompt: email failed seller_id=%s', seller_id)
    return True


def send_business_approval_notification_sync(seller_profile) -> None:
    """Push + email after admin approves business verification."""
    user = seller_profile.user
    PushNotificationService().send_push(
        user,
        'Biashara yako imethibitishwa',
        'Akaunti yako ya biashara imeidhinishwa. Viwango vya bidhaa na malipo vimesasishwa.',
        data={'type': 'business_verification_approved'},
    )
    if user.email:
        send_mail(
            'Business verification approved',
            f'Your business verification was approved. Higher limits are now active.\n{seller_dashboard_link()}\n',
            _outbound_email_from(),
            [user.email],
            fail_silently=True,
        )
def get_onboarding_completion_percentage(progress) -> int:
    """Calculate percentage of onboarding completion."""
    steps = [
        progress.step_registration,
        progress.step_store_setup,
        progress.step_id_submitted,
        progress.step_id_approved,
        progress.step_payout_added,
        progress.step_first_product,
    ]
    return int(round((sum(1 for s in steps if s) / 6) * 100))

def unpublish_seller_listings(user_id: int) -> int:
    """Unpublish all listings for a suspended or deleted seller."""
    return Listing.objects.filter(
        owner_id=user_id,
        deleted_at__isnull=True,
        is_published=True,
    ).update(is_published=False)

@transaction.atomic
def approve_seller_identity(seller_profile, admin_user, notes=''):
    """
    Admin workflow to approve a seller's identity documents.
    """
    iv = getattr(seller_profile, 'id_verification', None)
    if not iv:
        raise ValueError("No identity documents on file.")
        
    now = timezone.now()
    iv.reviewed_at = now
    iv.reviewed_by = admin_user
    iv.rejection_reason = ''
    if notes:
        iv.notes = notes
    iv.save()
    
    seller_profile.verification_status = 'verified'
    seller_profile.is_verified = True
    seller_profile.verified_at = now
    seller_profile.is_active = True
    seller_profile.save()
    
    return seller_profile

@transaction.atomic
def reject_seller_identity(seller_profile, admin_user, reason):
    """
    Admin workflow to reject a seller's identity documents.
    """
    iv = getattr(seller_profile, 'id_verification', None)
    if not iv:
        raise ValueError("No identity documents on file.")
        
    now = timezone.now()
    iv.reviewed_at = now
    iv.reviewed_by = admin_user
    iv.rejection_reason = reason
    iv.save()
    
    seller_profile.verification_status = 'rejected'
    seller_profile.is_verified = False
    seller_profile.verified_at = None
    seller_profile.save()
    
    return seller_profile
@transaction.atomic
def suspend_seller(seller_profile, admin_user, reason):
    """
    Suspend a seller account and hide their listings.
    """
    seller_profile.verification_status = 'suspended'
    seller_profile.is_active = False
    seller_profile.suspended_at = timezone.now()
    seller_profile.suspension_reason = reason
    seller_profile.save()
    
    # Unpublish listings
    unpublish_seller_listings(seller_profile.user_id)
    
    return seller_profile

@transaction.atomic
def reinstate_seller(seller_profile, admin_user, reason=''):
    """
    Reinstate a previously suspended seller.
    """
    seller_profile.verification_status = 'verified'
    seller_profile.is_active = True
    seller_profile.suspended_at = None
    seller_profile.suspension_reason = ''
    seller_profile.save()
    
    return seller_profile

@transaction.atomic
def approve_seller_business(seller_profile, admin_user):
    """
    Admin workflow to approve a seller's business verification.
    Increases limits and syncs business data.
    """
    bv = getattr(seller_profile, 'business_verification', None)
    if not bv or bv.status != 'pending':
        return seller_profile
        
    now = timezone.now()
    bv.status = 'approved'
    bv.reviewed_at = now
    bv.reviewed_by = admin_user
    bv.rejection_reason = ''
    bv.save()
    
    seller_profile.business_name = bv.business_name or seller_profile.business_name
    if bv.tin_number:
        seller_profile.tax_id = bv.tin_number
        
    seller_profile.business_type = 'business'
    seller_profile.is_business_verified = True
    seller_profile.products_limit = 500
    seller_profile.payout_limit = Decimal('0')
    seller_profile.save()
    
    progress, _ = SellerOnboardingProgress.objects.get_or_create(seller=seller_profile)
    progress.step_business_upgraded = True
    progress.save(update_fields=['step_business_upgraded'])
    
    return seller_profile

@transaction.atomic
def reject_seller_business(seller_profile, admin_user, reason):
    """
    Admin workflow to reject a seller's business verification.
    """
    bv = getattr(seller_profile, 'business_verification', None)
    if not bv or bv.status != 'pending':
        return seller_profile
        
    now = timezone.now()
    bv.status = 'rejected'
    bv.reviewed_at = now
    bv.reviewed_by = admin_user
    bv.rejection_reason = reason
    bv.save()
    
    return seller_profile
