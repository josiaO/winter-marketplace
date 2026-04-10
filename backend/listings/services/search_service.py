"""
listings.services.search_service
------------------------------
Service for handling listing searches and unified marketplace/property queries.
Supports Postgres full-text search and basic Q filtering.
"""
import logging
from django.db.models import Q
from django.conf import settings
from marketplace.models import MarketplaceItem

logger = logging.getLogger(__name__)

def unified_listing_search(query='', city=None, min_price=None, max_price=None):
    """
    Perform a unified search across MarketplaceItems.
    
    Returns:
        queryset: marketplace_items_queryset
    """
    # 1. Initialize base querysets
    items = MarketplaceItem.objects.filter(
        is_published=True,
        owner__isnull=False,
        owner__is_active=True
    ).select_related('owner', 'owner__seller_profile')

    # Filter out inactive seller profiles
    items = items.filter(
        Q(owner__seller_profile__isnull=True) | 
        Q(owner__seller_profile__is_active=True)
    )



    # 2. Apply Text Search
    if query:
        if 'postgresql' in settings.DATABASES['default']['ENGINE']:
            from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
            vector = SearchVector('title', weight='A') + SearchVector('description', weight='B')
            search_query = SearchQuery(query)

            items = items.annotate(
                rank=SearchRank(vector, search_query)
            ).filter(rank__gte=0.05).order_by('-rank')
        else:
            q_filter = Q(title__icontains=query) | Q(description__icontains=query)
            items = items.filter(q_filter)

    # 3. Apply Filters (City, Price)
    if city:
        items = items.filter(city__icontains=city)

    if min_price:
        items = items.filter(price__gte=min_price)

    if max_price:
        items = items.filter(price__lte=max_price)

    # 4. Final Ordering and Limiting (Views should handle pagination, but we provide a sensible default limit for unified views)
    items = items.order_by('-created_at')[:20]

    return items
