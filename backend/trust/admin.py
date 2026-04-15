"""
Trust Admin: UserVerification, ListingVerification, ReputationScore, PriceAnomaly
"""
from django.contrib import admin
from .models import (
    UserVerification,
    ListingVerification,
    ReputationScore,
    PriceAnomaly,
    Review,
    ReviewMedia,
    Report,
    TrustScore,
    ModerationAction,
)


@admin.register(UserVerification)
class UserVerificationAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'id_status', 'tin_status', 'business_license_status', 
        'is_identity_verified', 'verification_date'
    )
    list_select_related = ('user',)
    list_filter = (
        'id_status', 'tin_status', 'business_license_status',
        'is_identity_verified', 'verification_date'
    )
    search_fields = ('user__username', 'user__email', 'national_id_number', 'tin_number')
    readonly_fields = ('verification_date', 'created_at', 'updated_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('National ID', {
            'fields': ('national_id_number', 'national_id_front', 'national_id_back', 'id_status')
        }),
        ('TIN', {
            'fields': ('tin_number', 'tin_certificate', 'tin_status')
        }),
        ('Business License', {
            'fields': ('business_license_number', 'business_license_document', 'business_license_status')
        }),
        ('Global Verification', {
            'fields': ('is_identity_verified', 'verification_date', 'reviewer_notes')
        }),
    )
    
    actions = ['verify_users', 'unverify_users']
    
    def verify_users(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            is_identity_verified=True,
            verification_date=timezone.now()
        )
        self.message_user(request, "Selected users verified.")
    verify_users.short_description = "Verify selected users"
    
    def unverify_users(self, request, queryset):
        queryset.update(
            is_identity_verified=False,
            verification_date=None
        )
        self.message_user(request, "Selected users unverified.")
    unverify_users.short_description = "Unverify selected users"


@admin.register(ListingVerification)
class ListingVerificationAdmin(admin.ModelAdmin):
    list_display = (
        'listing_id', 'content_type', 'is_verified',
        'verified_by', 'created_at'
    )
    list_select_related = ('verified_by',)
    list_filter = ('is_verified', 'created_at')
    search_fields = ('listing_id', 'notes', 'verified_by__username')
    readonly_fields = ('created_at', 'updated_at')
    
    actions = ['verify_listings', 'unverify_listings']
    
    def verify_listings(self, request, queryset):
        queryset.update(
            is_verified=True,
            verified_by=request.user
        )
        self.message_user(request, "Selected listings verified.")
    verify_listings.short_description = "Verify selected listings"
    
    def unverify_listings(self, request, queryset):
        queryset.update(
            is_verified=False,
            verified_by=None
        )
        self.message_user(request, "Selected listings unverified.")
    unverify_listings.short_description = "Unverify selected listings"


@admin.register(ReputationScore)
class ReputationScoreAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'score', 'total_reviews', 'created_at', 'updated_at'
    )
    list_select_related = ('user',)
    list_filter = ('score', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Score', {
            'fields': ('score', 'total_reviews')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Note: ReputationScore is a simple model. For advanced trust scoring,
    # see TrustScore in trust.models


@admin.register(PriceAnomaly)
class PriceAnomalyAdmin(admin.ModelAdmin):
    list_display = (
        'listing', 'anomaly_type', 'score',
        'deviation_percentage', 'is_reviewed', 'created_at'
    )
    list_select_related = ('listing', 'reviewed_by')
    list_filter = (
        'anomaly_type', 'is_reviewed', 'score', 'created_at'
    )
    search_fields = (
        'listing__title', 'review_notes', 'reviewed_by__username'
    )
    readonly_fields = (
        'expected_price_range', 'actual_price', 'deviation_percentage',
        'reviewed_at', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Listing', {
            'fields': ('listing',)
        }),
        ('Anomaly Detection', {
            'fields': (
                'anomaly_type', 'score',
                'expected_price_range', 'actual_price', 'deviation_percentage'
            )
        }),
        ('Review', {
            'fields': (
                'is_reviewed', 'reviewed_by', 'review_notes', 'reviewed_at'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_reviewed', 'mark_unreviewed', 'detect_anomalies']
    
    def mark_reviewed(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            is_reviewed=True,
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(request, "Selected anomalies marked as reviewed.")
    mark_reviewed.short_description = "Mark as reviewed"
    
    def mark_unreviewed(self, request, queryset):
        queryset.update(
            is_reviewed=False,
            reviewed_by=None,
            reviewed_at=None
        )
        self.message_user(request, "Selected anomalies marked as unreviewed.")
    mark_unreviewed.short_description = "Mark as unreviewed"
    
    def detect_anomalies(self, request, queryset):
        from marketplace.services import PriceAnomalyService
        from listings.models import Listing
        count = 0
        for listing in Listing.objects.filter(is_published=True):
            anomaly = PriceAnomalyService.detect_price_anomaly(listing)
            if anomaly:
                count += 1
        self.message_user(request, f"Detected {count} price anomalies.")
    detect_anomalies.short_description = "Detect price anomalies for all listings"

class ReviewMediaInline(admin.TabularInline):
    model = ReviewMedia
    extra = 1


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'buyer', 'seller', 'rating', 'is_approved', 'created_at')
    list_select_related = ('order', 'buyer', 'seller')
    list_filter = ('rating', 'is_approved', 'is_flagged', 'is_hidden')
    search_fields = ('buyer__username', 'seller__username', 'comment')
    inlines = [ReviewMediaInline]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'reporter', 'report_type', 'reason', 'status', 'created_at')
    list_select_related = ('reporter',)
    list_filter = ('status', 'report_type', 'reason')
    search_fields = ('reporter__username', 'description')


@admin.register(TrustScore)
class TrustScoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'score', 'id_verified', 'tin_verified', 'license_verified', 'last_calculated_at')
    list_select_related = ('user',)
    list_filter = ('score', 'id_verified', 'tin_verified', 'license_verified')
    search_fields = ('user__username',)
    readonly_fields = ('last_calculated_at',)


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    list_display = ('target_user', 'action_type', 'target_type', 'moderator', 'is_active', 'created_at')
    list_select_related = ('target_user', 'moderator')
    list_filter = ('action_type', 'target_type', 'is_active')
    search_fields = ('target_user__username', 'reason')
