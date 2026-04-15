"""
Universal Listing Base Model
Everything being sold or rented is a Listing.
"""
from django.db import models
from django.conf import settings
from ..constants import ListingStatus
from django.utils.translation import gettext_lazy as _
from django.contrib.postgres.indexes import GinIndex
from .base import BaseModel
from django.db.models import Q

class BaseListing(BaseModel):
    """
    Abstract base model for all marketplace listings.
    
    Universal model that represents:
    - Products (phones, electronics, vehicles)
    - Services (cleaning, consulting, etc.)
    
    Category-specific attributes stored in `specs` JSONField.
    """
    # Ownership
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_listings",
        db_index=True,
        help_text="User who created this listing. Null if seller is deleted/banned."
    )

    store = models.ForeignKey(
        'marketplace.Store',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_listings",
        db_index=True,
        help_text="Storefront this listing belongs to. Null if store is deleted."
    )
    
    # Categorization
    category = models.ForeignKey(
        'catalog.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_listings",
        db_index=True,
        help_text="Category determines which dynamic fields are available"
    )
    
    # Basic Information
    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    
    # Pricing
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_index=True,
        help_text="Price in the specified currency"
    )
    currency = models.CharField(
        max_length=3,
        default='TZS',
        help_text="ISO 4217 currency code (TZS, USD, etc.)"
    )

    # Delivery (marketplace shipping quote — separate from item price)
    delivery_is_free = models.BooleanField(
        default=True,
        db_index=True,
        help_text="When True, buyers see free delivery; delivery_fee is ignored.",
    )
    delivery_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Delivery charge in listing currency when delivery_is_free is False",
    )
    
    # Listing Type
    LISTING_TYPES = (
        ('sale', _('For Sale')),
        ('rent', _('For Rent')),
        ('service', _('Service')),
    )
    listing_type = models.CharField(
        max_length=20,
        choices=LISTING_TYPES,
        default='sale',
        db_index=True
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=ListingStatus.choices,
        default=ListingStatus.DRAFT,
        db_index=True
    )
    
    # Inventory Management
    stock_quantity = models.PositiveIntegerField(
        default=1,
        help_text="Available stock quantity (1 for unique items, >1 for products)"
    )
    track_inventory = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether to track inventory for this listing"
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=0,
        help_text="Alert when stock falls below this threshold"
    )
    allow_backorders = models.BooleanField(
        default=False,
        help_text="Allow orders when out of stock"
    )
    
    # Location
    city = models.CharField(max_length=100, db_index=True, blank=True)
    region = models.CharField(max_length=100, blank=True, help_text="State/Region")
    address = models.CharField(max_length=300, blank=True)
    latitude = models.DecimalField(
        max_digits=20,
        decimal_places=12,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=20,
        decimal_places=12,
        null=True,
        blank=True
    )
    
    # Condition (for products)
    CONDITION_CHOICES = (
        ('new', _('New')),
        ('used', _('Used')),
        ('refurbished', _('Refurbished')),
        ('not_applicable', _('N/A')),
    )
    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default='new',
        db_index=True
    )
    
    # Publishing
    is_published = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Only published listings are visible to public"
    )
    view_count = models.PositiveIntegerField(default=0, db_index=True)
    
    # Dynamic Specifications (Category-specific attributes)
    specs = models.JSONField(
        default=dict,
        blank=True,
        help_text="Category-specific attributes (bedrooms, brand, etc.)"
    )
    
    # Soft Delete
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    
    # Verification
    is_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Admin-verified listing"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Promotion
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Promoted listing"
    )
    featured_at = models.DateTimeField(null=True, blank=True)
    
    # Trust & Safety Flags
    is_flagged = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flagged for review due to suspicious activity"
    )
    flagged_reason = models.TextField(
        blank=True,
        help_text="Reason for flagging"
    )
    flagged_at = models.DateTimeField(null=True, blank=True)
    price_anomaly_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Price anomaly detection score (0-1, higher = more suspicious)"
    )
    
    class Meta:
        abstract = True
        indexes = [
            # Category browsing
            models.Index(fields=['category', 'price', 'status']),
            # User listings
            models.Index(fields=['owner', 'status', '-created_at']),
            # Public listings
            models.Index(fields=['is_published', 'status', '-created_at']),
            # Location search
            models.Index(fields=['city', 'status']),
            # Inventory search
            models.Index(fields=['track_inventory', 'stock_quantity']),
            # Trust & safety
            models.Index(fields=['is_flagged', 'is_verified']),
            # JSONB index for specs filtering
            GinIndex(fields=['specs'], name='listing_specs_gin_idx'),
        ]
    
    def is_in_stock(self, quantity=1):
        """Check if listing has sufficient stock."""
        if not self.track_inventory:
            return True
        return self.stock_quantity >= quantity
    
    def reserve_stock(self, quantity=1):
        """Reserve stock (decrease available quantity)."""
        if not self.track_inventory:
            return True
        if self.stock_quantity < quantity:
            return False
        self.stock_quantity -= quantity
        self.save(update_fields=['stock_quantity'])
        return True
    
    def release_stock(self, quantity=1):
        """Release reserved stock (increase available quantity)."""
        if not self.track_inventory:
            return
        self.stock_quantity += quantity
        self.save(update_fields=['stock_quantity'])
    
    def is_low_stock(self):
        """Check if stock is below threshold."""
        if not self.track_inventory or self.low_stock_threshold == 0:
            return False
        return self.stock_quantity <= self.low_stock_threshold

    @property
    def is_ghost_listing(self):
        """
        Check if listing belongs to a deleted, banned, or inactive seller/store.
        Returns True if seller is unavailable (inactive/deleted), False if available.
        """
        # No owner = ghost listing
        if not self.owner_id:
            return True
        
        # Owner is inactive = ghost listing
        try:
            if not self.owner.is_active:
                return True
        except Exception:
            # Owner was deleted
            return True
        
        # Check seller profile - for marketplace listings, require active seller profile
        try:
            # Check if this is a marketplace listing
            # Marketplace items typically have stores, properties don't
            # Also check if MarketplaceItem exists for this listing
            is_marketplace_listing = False
            if hasattr(self, 'store_id') and self.store_id is not None:
                # Has a store - likely a marketplace item
                is_marketplace_listing = True
            else:
                # Use hasattr which utilizes select_related if available, avoiding N+1
                try:
                    is_marketplace_listing = hasattr(self, 'marketplaceitem')
                except Exception:
                    pass
            
            # Check seller profile status
            try:
                seller_profile = self.owner.seller_profile
                # Profile exists - check if it's active
                if not seller_profile.is_active:
                    return True  # Profile exists but is inactive = ghost
            except Exception:
                # Seller profile doesn't exist
                if is_marketplace_listing:
                    return True
                pass
        except Exception:
            # Any error - still try to check seller profile if it exists
            try:
                seller_profile = self.owner.seller_profile
                if not seller_profile.is_active:
                    return True
            except Exception:
                pass
            
        # Check if store exists and is active (only if store is assigned)
        # Don't require store to exist - not all listings need a store
        try:
            if self.store_id:
                # Store is assigned - check if it's active
                if hasattr(self, 'store') and self.store:
                    if not self.store.is_active:
                        return True  # Inactive store = ghost listing
        except Exception:
            # If we can't access store, that's OK - don't mark as ghost
            # The owner.is_active check above is sufficient
            pass

        # All checks passed - listing is available (seller is active)
        return False

    def get_similar_listings(self, limit=6):
        """
        Find similar listings in the same category.
        Excludes the current listing and all 'ghost' listings.
        Uses database-level filtering where possible for better performance.
        """
        if not self.category_id:
            return self.__class__.objects.none()
        
        # Get active listings in the same category with active owners
        queryset = self.__class__.objects.filter(
            category_id=self.category_id,
            is_published=True,
            status='active',
            owner__is_active=True,  # Filter out inactive owners
        ).exclude(id=self.id).select_related('owner', 'store', 'category')
        
        # For marketplace items, require active seller profile
        queryset = queryset.filter(
            owner__seller_profile__is_active=True
        )
        
        # Filter out listings with inactive stores (if store exists)
        queryset = queryset.filter(
            Q(store__isnull=True) | Q(store__is_active=True)
        )
        
        # Order by relevance: view count, then creation date
        queryset = queryset.order_by('-view_count', '-created_at')
        
        # Get the results
        similar = list(queryset[:limit])
        
        # Final filter in Python to ensure no ghost listings slip through
        # This is a safety net for edge cases
        filtered_similar = [item for item in similar if not item.is_ghost_listing]
        
        # If we got fewer than requested, try to get more from same parent category
        if len(filtered_similar) < limit and self.category and self.category.parent:
            parent_category_id = self.category.parent.id
            additional = self.__class__.objects.filter(
                category__parent_id=parent_category_id,
                is_published=True,
                status='active',
                owner__is_active=True,
            ).exclude(id=self.id).exclude(id__in=[s.id for s in filtered_similar])
            
            additional = additional.filter(owner__seller_profile__is_active=True)
            
            additional = additional.filter(
                Q(store__isnull=True) | Q(store__is_active=True)
            ).order_by('-view_count', '-created_at')[:limit - len(filtered_similar)]
            
            for item in additional:
                if not item.is_ghost_listing:
                    filtered_similar.append(item)
                    if len(filtered_similar) >= limit:
                        break
        
        return filtered_similar[:limit]
