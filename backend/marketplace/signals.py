import logging
# pylint: disable=no-member

from django.db.models.signals import post_save
from django.dispatch import receiver

from marketplace.models import MarketplaceItem, SellerPaymentMethod
from marketplace.tasks import sync_product_to_typesense

logger = logging.getLogger(__name__)


@receiver(post_save, sender=MarketplaceItem)
def sync_product_on_save(  # pylint: disable=unused-argument
    sender,
    instance: MarketplaceItem,
    created: bool,
    **kwargs,
):
    """Sync product to Typesense whenever it is created or updated."""
    try:
        sync_product_to_typesense.delay(instance.id)
        logger.info(
            "Queued Typesense sync for product %s (%s).",
            instance.id,
            "created" if created else "updated",
        )
    except Exception as exc:
        logger.exception(
            "Failed queuing Typesense sync for product %s: %s",
            instance.id,
            exc,
        )


@receiver(post_save, sender=SellerPaymentMethod)
def sync_payout_destination(sender, instance: SellerPaymentMethod, created: bool, **kwargs):
    """
    Sync seller payment method to escrow_engine.PayoutDestination.
    The provider key is passed through 1-to-1 — Selcom handles all channels,
    so no remapping is needed. The engine uses the same key to route payouts.
    """
    from escrow_engine.models.payout import PayoutDestination

    try:
        PayoutDestination.objects.update_or_create(
            user=instance.seller.user,
            method=instance.provider,      # exact key: mpesa, tigo_pesa, airtel_money, etc.
            account_number=instance.account_number,
            defaults={
                'account_name': instance.account_name,
                'is_default': instance.is_active,
            }
        )
        logger.info(
            "Synced PayoutDestination (%s) for seller %s",
            instance.provider, instance.seller.user.username,
        )
    except Exception as exc:
        logger.error(
            "Failed to sync PayoutDestination for seller %s: %s",
            instance.seller.user.username, exc,
        )
