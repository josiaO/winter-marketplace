import logging
from typing import Optional, List, Dict, Any
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from catalog.models import Category
from media_app.models import Media
from core.models import BaseListing

logger = logging.getLogger(__name__)

class MarketplaceService:
    """Centralized engine for marketplace operations across all verticals."""

    @staticmethod
    @transaction.atomic
    def create_listing(model_class, owner, data: Dict[str, Any], images: List = None) -> BaseListing:
        """Generic creation of any listing type with media attachments."""
        # 1. Handle category
        category_id = data.pop('category', None)
        category = None
        if category_id:
            category = Category.objects.filter(id=category_id).first()
        
        # 2. Extract specs (dynamic field values)
        specs = data.pop('specs', {})
        # Note: metadata was a legacy name in some parts of the service
        legacy_metadata = data.pop('metadata', {})
        if legacy_metadata:
            specs.update(legacy_metadata)
        
        # 3. Create listing
        listing = model_class.objects.create(
            owner=owner,
            category=category,
            specs=specs,
            **data
        )
        
        # 4. Handle media
        if images:
            MarketplaceService.attach_media(listing, images)
            
        return listing

    @staticmethod
    def attach_media(listing: BaseListing, files: List, media_type: str = 'image'):
        """Attach media files to any listing using generic relations."""
        content_type = ContentType.objects.get_for_model(listing)
        for i, file in enumerate(files):
            Media.objects.create(
                content_type=content_type,
                object_id=listing.id,
                file=file,
                media_type=media_type,
                order=i,
                is_main=(i == 0) # First image is main by default
            )

    @staticmethod
    def get_listing_media(listing: BaseListing) -> List[Media]:
        """Fetch all media for a listing."""
        content_type = ContentType.objects.get_for_model(listing)
        return Media.objects.filter(content_type=content_type, object_id=listing.id)

    @staticmethod
    def search_listings(model_class, filters: Dict[str, Any] = None):
        """Standardized search/filter logic for all verticals."""
        queryset = model_class.objects.filter(is_published=True)
        
        if not filters:
            return queryset
            
        # Common filters
        if 'city' in filters:
            queryset = queryset.filter(city__iexact=filters['city'])
        if 'category' in filters:
            queryset = queryset.filter(category_id=filters['category'])
        if 'min_price' in filters:
            queryset = queryset.filter(price__gte=filters['min_price'])
        if 'max_price' in filters:
            queryset = queryset.filter(price__lte=filters['max_price'])
        if 'condition' in filters:
            queryset = queryset.filter(condition=filters['condition'])
            
        # Dynamic Specs filters (searching inside JSON specs)
        for key, value in filters.items():
            if key.startswith('spec_'):
                spec_key = key.replace('spec_', '')
                queryset = queryset.filter(specs__contains={spec_key: value})
            elif key.startswith('meta_'): # Legacy support for meta_ filter prefix
                spec_key = key.replace('meta_', '')
                queryset = queryset.filter(specs__contains={spec_key: value})
                
        return queryset.order_by('-created_at')
