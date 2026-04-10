"""
Listings Admin: Listing, ListingMedia, ListingLike, ListingView
"""
from django.contrib import admin
from .models import Listing, ListingMedia, ListingLike, ListingView


class ListingMediaInline(admin.TabularInline):
    model = ListingMedia
    extra = 0
    fields = ('file', 'media_type', 'order', 'caption', 'created_at')
    readonly_fields = ('created_at',)
    can_delete = True


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'category', 'owner', 'price', 'currency',
        'status', 'listing_type', 'is_published',
        'stock_quantity', 'track_inventory', 'is_verified', 'created_at'
    )
    list_filter = (
        'category', 'status', 'listing_type', 'condition',
        'is_published', 'track_inventory', 'is_verified', 'is_flagged',
        'created_at'
    )
    search_fields = (
        'title', 'description', 'owner__username',
        'city', 'address'
    )
    readonly_fields = (
        'view_count', 'is_verified', 'verified_at',
        'is_flagged', 'flagged_at', 'price_anomaly_score',
        'created_at', 'updated_at'
    )
    inlines = [ListingMediaInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'owner', 'category', 'title', 'description'
            )
        }),
        ('Pricing', {
            'fields': ('price', 'currency', 'listing_type')
        }),
        ('Status', {
            'fields': ('status', 'is_published')
        }),
        ('Location', {
            'fields': (
                'city', 'region', 'address',
                'latitude', 'longitude'
            )
        }),
        ('Product Details', {
            'fields': ('condition',)
        }),
        ('Inventory', {
            'fields': (
                'stock_quantity', 'track_inventory',
                'low_stock_threshold', 'allow_backorders'
            )
        }),
        ('Specifications', {
            'fields': ('specs',),
            'classes': ('collapse',)
        }),
        ('Trust & Safety', {
            'fields': (
                'is_verified', 'verified_at',
                'is_flagged', 'flagged_reason', 'flagged_at',
                'price_anomaly_score'
            ),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('view_count',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'publish_listings', 'unpublish_listings',
        'verify_listings', 'flag_listings', 'unflag_listings'
    ]
    
    def publish_listings(self, request, queryset):
        queryset.update(is_published=True)
        self.message_user(request, "Selected listings published.")
    publish_listings.short_description = "Publish selected listings"
    
    def unpublish_listings(self, request, queryset):
        queryset.update(is_published=False)
        self.message_user(request, "Selected listings unpublished.")
    unpublish_listings.short_description = "Unpublish selected listings"
    
    def verify_listings(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            is_verified=True,
            verified_at=timezone.now()
        )
        self.message_user(request, "Selected listings verified.")
    verify_listings.short_description = "Verify selected listings"
    
    def flag_listings(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            is_flagged=True,
            flagged_at=timezone.now()
        )
        self.message_user(request, "Selected listings flagged.")
    flag_listings.short_description = "Flag selected listings"
    
    def unflag_listings(self, request, queryset):
        queryset.update(
            is_flagged=False,
            flagged_at=None,
            flagged_reason=''
        )
        self.message_user(request, "Selected listings unflagged.")
    unflag_listings.short_description = "Unflag selected listings"


@admin.register(ListingMedia)
class ListingMediaAdmin(admin.ModelAdmin):
    list_display = ('id', 'listing', 'media_type', 'order', 'file_preview', 'created_at')
    list_filter = ('media_type', 'created_at')
    search_fields = ('listing__title', 'caption')
    readonly_fields = ('file_preview', 'created_at', 'updated_at')
    
    def file_preview(self, obj):
        if obj.file:
            if obj.media_type == 'image':
                return f'<img src="{obj.file.url}" style="max-width: 100px; max-height: 100px;" />'
            else:
                return f'<a href="{obj.file.url}" target="_blank">Video</a>'
        return "No file"
    file_preview.allow_tags = True
    file_preview.short_description = 'Preview'


@admin.register(ListingLike)
class ListingLikeAdmin(admin.ModelAdmin):
    list_display = ('listing', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('listing__title', 'user__username')


@admin.register(ListingView)
class ListingViewAdmin(admin.ModelAdmin):
    list_display = ('listing', 'viewer', 'ip_address', 'viewed_at')
    list_filter = ('viewed_at',)
    search_fields = ('listing__title', 'viewer__username', 'ip_address')

