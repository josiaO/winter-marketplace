"""
trust.services.stats_service
---------------------------
Service for calculating trust-related statistics, ratings, and rankings.
"""
import logging
from django.db.models import Avg, Count
from trust.models import Review
from marketplace.models import SellerProfile

logger = logging.getLogger(__name__)

def get_listing_review_stats(listing_id):
    """
    Get review statistics for a specific listing.
    """
    reviews = Review.objects.filter(
        listing_id=listing_id,
        is_approved=True,
        is_hidden=False
    ).only('rating', 'id')
    
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    total_reviews = reviews.count()
    rating_distribution_qs = reviews.values('rating').annotate(count=Count('id'))
    rating_distribution = {r['rating']: r['count'] for r in rating_distribution_qs}
    recommend_base = reviews.filter(rating__gte=4).count()
    recommend_pct = round(100.0 * recommend_base / total_reviews) if total_reviews else None

    return {
        'average_rating': round(avg_rating, 2),
        'total_reviews': total_reviews,
        'verified_purchase_count': total_reviews,
        'recommend_percentage': recommend_pct,
        'rating_distribution': rating_distribution,
    }

def get_seller_review_stats(seller_id):
    """
    Get review statistics for a specific seller.
    """
    reviews = Review.objects.filter(
        seller_id=seller_id,
        is_approved=True,
        is_hidden=False
    ).only('rating', 'id')
    
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    total_reviews = reviews.count()
    rating_distribution_qs = reviews.values('rating').annotate(count=Count('id'))
    rating_distribution = {r['rating']: r['count'] for r in rating_distribution_qs}
    
    return {
        'average_rating': round(avg_rating, 2),
        'total_reviews': total_reviews,
        'rating_distribution': rating_distribution
    }

def get_most_rated_sellers(limit=20):
    """
    Get the most rated sellers for admin dashboard.
    Consolidates data from Review and SellerProfile.
    """
    
    # 1. Aggregate review data
    sellers_qs = Review.objects.filter(
        is_approved=True,
        is_hidden=False
    ).values('seller_id', 'seller__username').annotate(
        total_reviews=Count('id'),
        avg_rating=Avg('rating')
    ).order_by('-total_reviews', '-avg_rating')[:limit]
    
    sellers = list(sellers_qs)
    if not sellers:
        return []
    
    # 2. Match with SellerProfiles for business info
    seller_ids = [s['seller_id'] for s in sellers]
    profiles = SellerProfile.objects.filter(
        user_id__in=seller_ids
    ).select_related('user').only('user_id', 'business_name', 'is_verified')
    seller_profiles = {sp.user_id: sp for sp in profiles}
    
    # 3. Consolidate results
    result = []
    for seller in sellers:
        profile = seller_profiles.get(seller['seller_id'])
        result.append({
            'seller_id': seller['seller_id'],
            'username': seller['seller__username'],
            'business_name': profile.business_name if profile else None,
            'total_reviews': seller['total_reviews'],
            'average_rating': round(seller['avg_rating'] or 0, 2),
            'is_verified': profile.is_verified if profile else False,
        })
    
    return result
