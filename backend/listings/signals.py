import logging
# pylint: disable=no-member

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from listings.models import Listing, ListingMedia
from marketplace.models import MarketplaceItem
from marketplace.tasks import moderate_product_image

logger = logging.getLogger(__name__)

_LOW_STOCK_CACHE_PREFIX = 'listing_low_stock_push:'


@receiver(post_save, sender=Listing)
def notify_seller_on_low_stock(sender, instance: Listing, **kwargs):
    """Notify listing owner once per day when tracked stock is at or below threshold."""
    if not instance.track_inventory or not instance.low_stock_threshold:
        return
    if instance.stock_quantity > instance.low_stock_threshold:
        cache.delete(f'{_LOW_STOCK_CACHE_PREFIX}{instance.pk}')
        return

    cache_key = f'{_LOW_STOCK_CACHE_PREFIX}{instance.pk}'
    if cache.get(cache_key):
        return

    try:
        from commerce.seller_notifications import notify_seller_low_stock

        notify_seller_low_stock(
            instance.owner,
            instance.title or 'Product',
            int(instance.stock_quantity),
            instance.pk,
        )
        cache.set(cache_key, 1, timeout=86400)
    except Exception:
        logger.exception('Low stock notification failed listing_id=%s', instance.pk)


@receiver(post_save, sender=ListingMedia)
def moderate_uploaded_product_image(  # pylint: disable=unused-argument
    sender,
    instance: ListingMedia,
    created: bool,
    **kwargs,
):
    """Run image moderation asynchronously after product image upload."""
    if not created or instance.media_type != "image":
        return

    listing_id = instance.listing_id
    is_marketplace_item = MarketplaceItem.objects.filter(id=listing_id).exists()
    if not is_marketplace_item:
        return

    try:
        moderate_product_image.delay(listing_id)
        logger.info(
            "Queued moderation for product image upload. product_id=%s",
            listing_id,
        )
    except Exception as exc:
        logger.exception(
            "Failed to queue moderation for product %s: %s",
            listing_id,
            exc,
        )
