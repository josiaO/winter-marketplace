import logging
# pylint: disable=no-member

from django.db.models.signals import post_save
from django.dispatch import receiver

from listings.models import ListingMedia
from marketplace.models import MarketplaceItem
from marketplace.tasks import moderate_product_image

logger = logging.getLogger(__name__)


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
