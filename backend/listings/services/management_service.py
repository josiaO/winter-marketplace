"""
listings.services.management_service
-----------------------------------
Service for administrative actions on listings, such as verification and featuring.
"""
import logging
from django.utils import timezone
from listings.models import Listing

logger = logging.getLogger(__name__)

def toggle_listing_verification(listing: Listing, is_verified: bool = None):
    """
    Toggle or set the verification status of a listing.
    """
    if is_verified is None:
        is_verified = not listing.is_verified
    
    listing.is_verified = is_verified
    if is_verified:
        listing.verified_at = timezone.now()
    else:
        listing.verified_at = None
    
    listing.save(update_fields=['is_verified', 'verified_at'])
    logger.info(f"Listing {listing.id} verification set to {is_verified}")
    return listing

def toggle_listing_featured(listing: Listing, is_featured: bool = None):
    """
    Toggle or set the featured status of a listing.
    """
    if is_featured is None:
        is_featured = not listing.is_featured
    
    listing.is_featured = is_featured
    if is_featured:
        listing.featured_at = timezone.now()
    else:
        listing.featured_at = None
    
    listing.save(update_fields=['is_featured', 'featured_at'])
    logger.info(f"Listing {listing.id} featured set to {is_featured}")
    return listing
