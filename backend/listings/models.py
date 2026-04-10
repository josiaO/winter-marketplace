from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.models.base import BaseListing, BaseModel

class Listing(BaseListing):
    """
    Canonical product row for the platform: price, inventory (`stock_quantity`,
    `track_inventory`, …), media, and publishing live here.

    Marketplace products use **multi-table inheritance**: `marketplace.MarketplaceItem`
    subclasses this model (same primary key). There is a single inventory source — these
    fields — not a duplicate table. `commerce.services.inventory.InventoryService` / checkout always updates `Listing`.
    """
    class Meta:
        verbose_name = _("Listing")
        verbose_name_plural = _("Listings")
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['is_published', 'category', 'owner'],
                name='listings_list_pub_cat_owner',
            ),
        ]

    def __str__(self):
        return self.title

class ListingMedia(BaseModel):
    """Media associated with a listing."""
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='media')
    file = models.FileField(upload_to='listings/media/')
    media_type = models.CharField(
        max_length=10, 
        choices=(('image', 'Image'), ('video', 'Video')), 
        default='image'
    )
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Listing Media")
        verbose_name_plural = _("Listing Media Items")
        ordering = ['order', 'created_at']

class ListingLike(models.Model):
    """Universal like/favorite system for listings."""
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='liked_listings')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('listing', 'user')
        ordering = ['-created_at']

class ListingView(models.Model):
    """Tracks views for listings."""
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='views_history')
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='listing_views'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-viewed_at']
