import logging
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError
from ..models import Listing, ListingView, ListingMedia
from ..validators import validate_media_file

logger = logging.getLogger(__name__)

@transaction.atomic
def create_listing(owner, data, media_files=None):
    """Business logic for creating a listing and its media."""
    # The actual instance creation should be done via serializer in view to leverage DRF validation,
    # but we handle the post-creation logic here (like media).
    # NOTE: In our case, the view already creates the listing, we just handle media.
    return None

def handle_listing_media(listing: Listing, media_files: list, append: bool = True) -> int:
    """
    Saves and associates media files with a listing.
    """
    if not media_files:
        return 0
    
    # Get current max order if appending
    max_order = -1
    if append:
        existing = listing.media.all()
        max_order = max([m.order for m in existing], default=-1)
    else:
        # If not appending, clear existing (optional, but for now we follow view logic)
        pass

    saved_count = 0
    for index, media_file in enumerate(media_files):
        try:
            # Validate
            _, media_type = validate_media_file(media_file)
            
            # Create
            media_obj = ListingMedia.objects.create(
                listing=listing,
                file=media_file,
                media_type=media_type,
                order=max_order + index + 1
            )
            saved_count += 1
            logger.info(f"Saved media file {index}: {media_file.name} as {media_type} (ID: {media_obj.id})")
        except Exception as e:
            logger.error(f"Failed to save media file {index} ({media_file.name}): {str(e)}")
            
    return saved_count

def publish_listing(listing_id):
    """Publish a listing."""
    listing = get_object_or_404(Listing, id=listing_id)
    listing.is_published = True
    listing.save(update_fields=['is_published', 'updated_at'])
    return listing

def archive_listing(listing_id):
    """Archive a listing (mark as sold/rented or inactive)."""
    listing = get_object_or_404(Listing, id=listing_id)
    listing.status = 'inactive'  # Or 'sold'/'rented' based on logic
    listing.save(update_fields=['status'])
    return listing

def increment_views(listing, user=None, ip_address=None):
    """Increment view count and track view history."""
    # Simple increment
    listing.view_count += 1
    listing.save(update_fields=['view_count'])
    
    # Track history
    ListingView.objects.create(
        listing=listing,
        viewer=user if user and user.is_authenticated else None,
        ip_address=ip_address
    )
    return listing
