import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from marketplace.models import MarketplaceItem, SellerProfile
from listings.models import Listing as ListingModel
from sellers.models import SellerOnboardingProgress
from sellers.tasks import send_business_upgrade_prompt, send_seller_approval_email, send_seller_verified_push

logger = logging.getLogger(__name__)


@receiver(post_save, sender=SellerProfile)
def ensure_onboarding_progress(sender, instance, created, **kwargs):
    if created:
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

        # Automatically activate and publish any draft listings
        try:
            from core.constants import ListingStatus
            ListingModel.objects.filter(
                owner=instance.user,
                status=ListingStatus.DRAFT
            ).update(
                status=ListingStatus.ACTIVE,
                is_published=True
            )
            logger.info("Activated draft listings for seller %s after verification", instance.pk)
        except Exception:
            logger.exception('seller_profile_after_save: failed to activate draft items for seller %s', instance.pk)

        send_seller_verified_push.delay(instance.pk)
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
def mark_first_product(sender, instance, created, **kwargs):
    if not created:
        return
    if not instance.owner_id:
        return
    try:
        sp = instance.owner.seller_profile
    except SellerProfile.DoesNotExist:
        return
        
    try:
        progress = SellerOnboardingProgress.objects.get(seller=sp)
        if not progress.step_first_product:
            progress.step_first_product = True
            progress.save(update_fields=['step_first_product'])
    except SellerOnboardingProgress.DoesNotExist:
        # Should not typically happen if seller profile signals triggered, but handle anyway
        progress = SellerOnboardingProgress.objects.create(
            seller=sp, step_registration=True, step_first_product=True
        )


def _mark_first_product_for_owner(owner):
    """Shared helper: mark step_first_product for a seller by their user object."""
    if not owner:
        return
    try:
        sp = owner.seller_profile
    except SellerProfile.DoesNotExist:
        return
    try:
        progress = SellerOnboardingProgress.objects.get(seller=sp)
        if not progress.step_first_product:
            progress.step_first_product = True
            progress.save(update_fields=['step_first_product'])
            logger.info('step_first_product set for seller_id=%s via Listing', sp.pk)
    except SellerOnboardingProgress.DoesNotExist:
        SellerOnboardingProgress.objects.create(
            seller=sp, step_registration=True, step_first_product=True
        )
        logger.info('SellerOnboardingProgress created with step_first_product for seller_id=%s', sp.pk)


@receiver(post_save, sender=ListingModel)
def mark_first_product_from_listing(sender, instance, created, **kwargs):
    """Mark step_first_product when a Listing is created (used by the seller listing form)."""
    if not created:
        return
    _mark_first_product_for_owner(instance.owner)
