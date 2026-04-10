"""
Marketplace Admin: SellerProfile, Store, StoreFollow
"""
from django.contrib import admin
from .models import (
    SellerProfile,
    Store,
    StoreFollow,
    MarketplaceItem,
    ProductModerationLog,
)


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'business_name', 'business_type', 'is_verified',
        'average_rating', 'total_reviews', 'total_sales', 'is_active'
    )
    list_filter = ('business_type', 'is_verified', 'is_active', 'created_at')
    search_fields = (
        'user__username', 'user__email', 'business_name',
        'business_phone', 'business_email'
    )
    readonly_fields = (
        'average_rating', 'total_reviews', 'total_sales',
        'verified_at', 'suspended_at',
        'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Business Information', {
            'fields': (
                'business_name', 'business_type', 'tax_id'
            )
        }),
        ('Contact', {
            'fields': (
                'business_phone', 'business_email', 'business_address'
            )
        }),
        ('Verification', {
            'fields': (
                'verification_status',
                'is_verified',
                'verified_at',
                'verification_documents',
            )
        }),
        ('Statistics', {
            'fields': (
                'average_rating', 'total_reviews', 'total_sales'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': (
                'is_active', 'suspended_at', 'suspension_reason'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['verify_sellers', 'suspend_sellers', 'activate_sellers', 'update_ratings']
    
    def verify_sellers(self, request, queryset):
        from marketplace.services.seller_service import SellerService

        for seller in queryset:
            SellerService.verify_by_admin(seller)
        self.message_user(request, "Selected sellers verified.")
    verify_sellers.short_description = "Verify selected sellers"
    
    def suspend_sellers(self, request, queryset):
        from marketplace.services.seller_service import SellerService

        for seller in queryset:
            SellerService.suspend_by_admin(seller, reason='Bulk suspend from admin')
        self.message_user(request, "Selected sellers suspended.")
    suspend_sellers.short_description = "Suspend selected sellers"
    
    def activate_sellers(self, request, queryset):
        from marketplace.services.seller_service import SellerService

        for seller in queryset:
            if seller.verification_status == 'suspended':
                SellerService.reopen_after_suspension(seller)
            else:
                SellerService.refresh_flags_from_verification_status(seller)
        self.message_user(request, "Selected sellers re-activated or re-opened for review.")
    activate_sellers.short_description = "Activate selected sellers"
    
    def update_ratings(self, request, queryset):
        from marketplace.services.seller_service import SellerService

        for seller in queryset:
            SellerService.update_seller_ratings(seller)
        self.message_user(request, "Ratings updated for selected sellers.")
    update_ratings.short_description = "Update ratings"


class StoreFollowInline(admin.TabularInline):
    model = StoreFollow
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'seller', 'is_active', 'is_featured',
        'total_listings', 'total_sales', 'total_followers'
    )
    list_filter = ('is_active', 'is_featured', 'created_at')
    search_fields = (
        'name', 'slug', 'seller__user__username',
        'contact_email', 'contact_phone'
    )
    
    def get_prepopulated_fields(self, request, obj=None):
        """Only prepopulate slug when creating new store."""
        if obj is None:  # Creating a new store
            return {'slug': ('name',)}
        return {}  # Don't prepopulate when editing
    
    def get_readonly_fields(self, request, obj=None):
        """Make slug readonly when editing existing store."""
        readonly = [
            'total_listings', 'total_sales', 'total_followers',
            'created_at', 'updated_at'
        ]
        if obj:  # Editing an existing store
            readonly.append('slug')
        return readonly
    
    fieldsets = (
        ('Store Information', {
            'fields': ('seller', 'name', 'slug', 'description')
        }),
        ('Branding', {
            'fields': ('logo', 'banner')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_featured')
        }),
        ('Contact', {
            'fields': ('contact_email', 'contact_phone', 'website')
        }),
        ('Social Media', {
            'fields': ('social_links',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'total_listings', 'total_sales', 'total_followers'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['feature_stores', 'unfeature_stores', 'update_statistics']
    
    def feature_stores(self, request, queryset):
        queryset.update(is_featured=True)
        self.message_user(request, "Selected stores featured.")
    feature_stores.short_description = "Feature selected stores"
    
    def unfeature_stores(self, request, queryset):
        queryset.update(is_featured=False)
        self.message_user(request, "Selected stores unfeatured.")
    unfeature_stores.short_description = "Unfeature selected stores"
    
    def update_statistics(self, request, queryset):
        from marketplace.services.store_service import update_store_statistics

        for store in queryset:
            update_store_statistics(store)
        self.message_user(request, "Statistics updated for selected stores.")
    update_statistics.short_description = "Update statistics"


@admin.register(StoreFollow)
class StoreFollowAdmin(admin.ModelAdmin):
    list_display = ('user', 'store', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'store__name')


@admin.register(MarketplaceItem)
class MarketplaceItemAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'category', 'owner', 'price', 'currency',
        'status', 'is_published', 'stock_quantity', 'created_at'
    )
    list_filter = (
        'category', 'status', 'listing_type', 'condition',
        'is_published', 'track_inventory', 'created_at'
    )
    search_fields = ('title', 'description', 'owner__username')
    readonly_fields = (
        'view_count', 'is_verified', 'verified_at',
        'is_flagged', 'flagged_at', 'price_anomaly_score',
        'created_at', 'updated_at'
    )


@admin.register(ProductModerationLog)
class ProductModerationLogAdmin(admin.ModelAdmin):
    list_display = ("product", "is_safe", "moderated_at")
    list_filter = ("is_safe", "moderated_at")
    search_fields = ("product__title", "image_url")
    readonly_fields = ("moderated_at", "created_at", "updated_at")

