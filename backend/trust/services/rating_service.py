"""
trust.services.rating_service
----------------------------
Recalculate seller ratings and handle order reviews.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import Avg
from trust.models import Review
from marketplace.models import SellerProfile

logger = logging.getLogger(__name__)


def update_seller_rating(seller):
    """
    Recalculate seller rating from reviews.
    """
    # Get seller profile or create if doesn't exist
    seller_profile, _ = SellerProfile.objects.get_or_create(user=seller)
    
    # Get all non-hidden, approved reviews for this seller
    reviews = Review.objects.filter(
        seller=seller,
        is_hidden=False,
        is_approved=True
    )
    
    total = reviews.count()
    
    if total == 0:
        seller_profile.average_rating = 0.0
        seller_profile.total_reviews = 0
    else:
        # Calculate average rating
        avg = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0.0
        seller_profile.average_rating = round(float(avg), 2)
        seller_profile.total_reviews = total
    
    seller_profile.save(update_fields=['average_rating', 'total_reviews'])
    logger.info("Recalculated rating for seller %s: %s (%s reviews)", seller.id, seller_profile.average_rating, total)
    return seller_profile.average_rating, seller_profile.total_reviews


@transaction.atomic
def create_order_review(order, buyer, rating, comment=''):
    """
    Create a review for an order and update seller rating.
    """
    if order.buyer != buyer:
        raise ValueError("Only the buyer of the order can create a review.")
    
    if order.status != 'delivered':
        raise ValueError("Order must be in 'delivered' status.")
    
    # Check if review already exists
    if Review.objects.filter(order=order).exists():
        raise ValueError("A review already exists for this order.")
    
    # Create review
    review = Review.objects.create(
        order=order,
        seller=order.seller,
        buyer=buyer,
        rating=rating,
        comment=comment,
        listing=order.items.first().listing if order.items.exists() else None
    )
    
    # Update seller rating
    update_seller_rating(order.seller)
    
    return review
