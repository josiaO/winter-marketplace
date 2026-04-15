import logging

from celery import shared_task

from sellers import services
from marketplace.models import SellerProfile
from sellers.models import SellerPayoutAccount

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_seller_approval_email(self, seller_id):
    try:
        sp = SellerProfile.objects.select_related('user').get(pk=seller_id)
    except SellerProfile.DoesNotExist:
        return
    try:
        services.send_seller_approval_email_sync(sp)
    except Exception as exc:
        logger.exception('send_seller_approval_email failed')
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_seller_rejection_email(self, seller_id, rejection_reason):
    try:
        sp = SellerProfile.objects.select_related('user').get(pk=seller_id)
    except SellerProfile.DoesNotExist:
        return
    try:
        services.send_seller_rejection_email_sync(sp, rejection_reason)
    except Exception as exc:
        logger.exception('send_seller_rejection_email failed')
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_seller_suspension_email(self, seller_id, reason):
    try:
        sp = SellerProfile.objects.select_related('user').get(pk=seller_id)
    except SellerProfile.DoesNotExist:
        return
    try:
        services.send_seller_suspension_email_sync(sp, reason)
    except Exception as exc:
        logger.exception('send_seller_suspension_email failed')
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_admin_new_verification(self, seller_id):
    try:
        sp = SellerProfile.objects.select_related('user').get(pk=seller_id)
    except SellerProfile.DoesNotExist:
        return
    try:
        services.notify_staff_new_identity_verification_sync(sp)
    except Exception as exc:
        logger.exception('notify_admin_new_verification failed')
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_payout_verification(self, payout_account_id):
    try:
        acct = SellerPayoutAccount.objects.select_related('seller', 'seller__user').get(
            pk=payout_account_id
        )
    except SellerPayoutAccount.DoesNotExist:
        return
    try:
        services.run_payout_verification_disbursement(acct)
    except Exception as exc:
        logger.exception('send_payout_verification failed')
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_business_upgrade_prompt(self, seller_id):
    try:
        services.try_send_business_upgrade_prompt(seller_id)
    except Exception:
        logger.exception('send_business_upgrade_prompt failed seller_id=%s', seller_id)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_admin_business_verification(self, seller_id):
    try:
        sp = SellerProfile.objects.select_related('user').get(pk=seller_id)
    except SellerProfile.DoesNotExist:
        return
    try:
        services.notify_staff_business_verification_sync(sp)
    except Exception as exc:
        logger.exception('notify_admin_business_verification failed')
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_business_approval_notification(self, seller_id):
    try:
        sp = SellerProfile.objects.select_related('user').get(pk=seller_id)
    except SellerProfile.DoesNotExist:
        return
    try:
        services.send_business_approval_notification_sync(sp)
    except Exception as exc:
        logger.exception('send_business_approval_notification failed')
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_seller_verified_push(self, seller_id):
    try:
        sp = SellerProfile.objects.select_related('user').get(pk=seller_id)
    except SellerProfile.DoesNotExist:
        return
    try:
        from core.services.notifications import PushNotificationService
        PushNotificationService().send_push(
            sp.user,
            'Hongera! Akaunti yako imeidhinishwa',
            'Duka lako sasa linaonekana kwa wanunuzi Tanzania nzima.',
            data={'type': 'seller_verified', 'seller_id': str(sp.pk)},
        )
    except Exception as exc:
        logger.exception('send_seller_verified_push failed')
        raise self.retry(exc=exc, countdown=60)
