import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from marketplace.models import MarketplaceItem, SellerProfile
from sellers.models import SellerOnboardingProgress
from sellers.tasks import send_business_upgrade_prompt, send_seller_approval_email

logger = logging.getLogger(__name__)


@receiver(post_save, sender=SellerProfile)
def ensure_onboarding_progress(sender, instance, created, **kwargs):
    progress, _ = SellerOnboardingProgress.objects.get_or_create(seller=instance)
    if not progress.step_registration:
        progress.step_registration = True
        progress.save(update_fields=['step_registration'])


@receiver(post_save, sender=SellerProfile)
def ensure_marketplace_store_for_seller(sender, instance, **kwargs):
    """Every seller profile has at least one marketplace Store row (created or backfilled)."""
    if instance.stores.exists():
        return
    try:
        from marketplace.services import ensure_default_store_for_seller

        ensure_default_store_for_seller(instance)
    except Exception:
        logger.exception(
            'ensure_marketplace_store_for_seller failed seller_id=%s',
            instance.pk,
        )


@receiver(pre_save, sender=SellerProfile)
def seller_profile_cache_state(sender, instance, **kwargs):
    instance._presale_verification_status = None
    instance._presale_total_sales = None
    instance._presale_completed_orders = None
    if not instance.pk:
        return
    try:
        prev = SellerProfile.objects.get(pk=instance.pk)
        instance._presale_verification_status = prev.verification_status
        instance._presale_total_sales = prev.total_sales
        instance._presale_completed_orders = prev.completed_orders
    except SellerProfile.DoesNotExist:
        pass


@receiver(post_save, sender=SellerProfile)
def seller_profile_after_save(sender, instance, **kwargs):
    old_vs = getattr(instance, '_presale_verification_status', None)
    if old_vs != 'verified' and instance.verification_status == 'verified':
        try:
            progress, _ = SellerOnboardingProgress.objects.get_or_create(seller=instance)
            if not progress.step_id_approved:
                progress.step_id_approved = True
                progress.save(update_fields=['step_id_approved'])
        except Exception:
            logger.exception('seller_profile_after_save: progress update failed')

        from core.services.notifications import PushNotificationService

        PushNotificationService().send_push(
            instance.user,
            'Hongera! Akaunti yako imeidhinishwa',
            'Duka lako sasa linaonekana kwa wanunuzi Tanzania nzima.',
            data={'type': 'seller_verified', 'seller_id': str(instance.pk)},
        )
        send_seller_approval_email.delay(instance.pk)

    try:
        progress = instance.onboarding_progress
    except SellerOnboardingProgress.DoesNotExist:
        progress = None
    if (
        progress
        and not progress.step_business_upgraded
        and not progress.upgrade_prompt_sent
        and (
            instance.total_sales >= 500000
            or instance.completed_orders >= 20
        )
    ):
        old_ts = getattr(instance, '_presale_total_sales', None)
        old_co = getattr(instance, '_presale_completed_orders', None)
        crossed = False
        if instance.total_sales >= 500000:
            crossed = old_ts is None or old_ts < 500000
        if instance.completed_orders >= 20:
            crossed = crossed or (old_co is None or old_co < 20)
        if crossed:
            send_business_upgrade_prompt.delay(instance.pk)


@receiver(post_save, sender=MarketplaceItem)
def mark_first_product(sender, instance, **kwargs):
    if not instance.owner_id:
        return
    try:
        sp = instance.owner.seller_profile
    except SellerProfile.DoesNotExist:
        return
    progress, _ = SellerOnboardingProgress.objects.get_or_create(seller=sp)
    if not progress.step_first_product:
        progress.step_first_product = True
        progress.save(update_fields=['step_first_product'])
