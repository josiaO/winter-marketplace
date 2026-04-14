"""
trust.services.verification_service
---------------------------------
Service for listing verification and user verification workflows.
"""
import logging
from django.utils import timezone
from django.db import transaction
from trust.models import ListingVerification, TrustScore
from listings.models import Listing

logger = logging.getLogger(__name__)

@transaction.atomic
def verify_listing(verification_id, admin_user):
    """
    Verify a listing and update the Listing instance.
    """
    verification = ListingVerification.objects.get(pk=verification_id)
    verification.is_verified = True
    verification.verified_by = admin_user
    verification.save()
    
    # Update linked listing
    try:
        listing = Listing.objects.get(id=verification.listing_id)
        listing.is_verified = True
        listing.verified_at = timezone.now()
        listing.save(update_fields=['is_verified', 'verified_at'])
        logger.info(f"Listing {listing.id} verified by {admin_user.username}")
    except Listing.DoesNotExist:
        logger.warning(f"Listing {verification.listing_id} missing during verification")
        
    return verification

@transaction.atomic
def unverify_listing(verification_id, admin_user):
    """
    Remove verification status from a listing.
    """
    verification = ListingVerification.objects.get(pk=verification_id)
    verification.is_verified = False
    verification.verified_by = None
    verification.save()
    
    # Update linked listing
    try:
        listing = Listing.objects.get(id=verification.listing_id)
        listing.is_verified = False
        listing.verified_at = None
        listing.save(update_fields=['is_verified', 'verified_at'])
        logger.info(f"Listing {listing.id} unverified by {admin_user.username}")
    except Listing.DoesNotExist:
        logger.warning(f"Listing {verification.listing_id} missing during unverification")
        
    return verification


def update_user_trust_score(user, **kwargs):
    """
    Helper to update or create user trust score factors.
    """
    score_obj, _ = TrustScore.objects.get_or_create(user=user)
    
    for key, value in kwargs.items():
        if hasattr(score_obj, key):
            setattr(score_obj, key, value)
    
    score_obj.calculate_score()
    score_obj.save()
    return score_obj


@transaction.atomic
def verify_user_document(verification, doc_type, status='verified', notes='', admin_user=None):
    """
    Admin action to verify a specific document for a user.
    """
    if doc_type == 'id':
        verification.id_status = status
        if status == 'verified':
            verification.is_identity_verified = True
            verification.verification_date = timezone.now()
        else:
            verification.is_identity_verified = False
            
    elif doc_type == 'tin':
        verification.tin_status = status
    elif doc_type == 'license':
        verification.business_license_status = status
    
    # Update global business verified status
    # Note: Logic can be adjusted (e.g. requires BOTH tin and license verified)
    if verification.tin_status == 'verified' and verification.business_license_status == 'verified':
        verification.is_business_verified = True
    else:
        verification.is_business_verified = False
    
    if notes:
        verification.reviewer_notes = notes
    
    verification.save()
    
    # Update trust score accordingly
    update_user_trust_score(
        verification.user, 
        id_verified=(verification.id_status == 'verified'),
        tin_verified=(verification.tin_status == 'verified'),
        license_verified=(verification.business_license_status == 'verified')
    )
    
    return verification
