from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from .constants import (
    UserVerificationStatus,
    ReportStatus
)
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models.base import BaseModel


# ---------------------------------------------------------------------------
# Verification, listing checks, reputation, pricing
# ---------------------------------------------------------------------------


class UserVerification(BaseModel):
    """Enhanced trust verification for sellers (TIN, National ID, Business License)."""
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='verification')

    # National ID / Passport
    ID_TYPE_CHOICES = (
        ('national_id', _('National ID')),
        ('passport', _('Passport')),
        ('voters_card', _("Voter's card")),
        ('driving_license', _('Driving license')),
    )
    id_type = models.CharField(max_length=30, choices=ID_TYPE_CHOICES, blank=True, null=True)
    id_number = models.CharField(max_length=50, blank=True, null=True) # Unified field
    
    national_id_front = models.FileField(upload_to='verifications/id/', blank=True, null=True)
    national_id_back = models.FileField(upload_to='verifications/id/', blank=True, null=True)
    selfie_with_id = models.ImageField(upload_to='verifications/selfies/', blank=True, null=True)
    
    id_status = models.CharField(
        max_length=20, 
        choices=UserVerificationStatus.choices, 
        default=UserVerificationStatus.NOT_SUBMITTED
    )

    # TIN
    tin_number = models.CharField(max_length=50, blank=True, null=True)
    tin_certificate = models.FileField(upload_to='verifications/id/', blank=True, null=True) # Unified path
    tin_status = models.CharField(
        max_length=20, 
        choices=UserVerificationStatus.choices, 
        default=UserVerificationStatus.NOT_SUBMITTED
    )

    # Business License
    business_license_number = models.CharField(max_length=50, blank=True, null=True)
    business_license_document = models.FileField(upload_to='verifications/id/', blank=True, null=True) # Unified path
    business_license_status = models.CharField(
        max_length=20, 
        choices=UserVerificationStatus.choices, 
        default=UserVerificationStatus.NOT_SUBMITTED
    )

    # Global verification status
    is_identity_verified = models.BooleanField(default=False)
    is_business_verified = models.BooleanField(default=False) # Tier 2
    verification_date = models.DateTimeField(null=True, blank=True)

    # Legacy field - keeping for compatibility
    document_type = models.CharField(max_length=50, blank=True)
    national_id_number = models.CharField(max_length=50, blank=True, null=True) # Kept for migration

    # Admin review
    reviewer_notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Verification for {self.user.username} (ID: {self.id_status}, TIN: {self.tin_status})"


class ListingVerification(BaseModel):
    """Deep verification for high-value listings (e.g. Real Estate, Vehicles)."""
    listing_id = models.PositiveIntegerField()
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    is_verified = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Verification for Listing #{self.listing_id}"


class ReputationScore(BaseModel):
    """Aggregated trust score for sellers."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reputation')
    score = models.FloatField(default=0.0)
    total_reviews = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} Reputation: {self.score}"


class PriceAnomaly(BaseModel):
    """
    Price anomaly detection records.
    Tracks suspicious pricing patterns that may indicate scams.
    """
    listing = models.ForeignKey(
        'listings.Listing',
        on_delete=models.CASCADE,
        related_name='price_anomalies'
    )

    # Anomaly Detection
    anomaly_type = models.CharField(
        max_length=50,
        choices=(
            ('too_low', _('Suspiciously Low Price')),
            ('too_high', _('Suspiciously High Price')),
            ('price_drop', _('Sudden Price Drop')),
            ('price_spike', _('Sudden Price Spike')),
            ('category_mismatch', _('Price Mismatch with Category')),
        ),
        db_index=True
    )
    score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Anomaly score (0-1, higher = more suspicious)"
    )

    # Context
    expected_price_range = models.JSONField(
        default=dict,
        blank=True,
        help_text="Expected price range based on similar listings"
    )
    actual_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    deviation_percentage = models.FloatField(
        help_text="Percentage deviation from expected price"
    )

    # Status
    is_reviewed = models.BooleanField(
        default=False,
        db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_anomalies'
    )
    review_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Price Anomaly")
        verbose_name_plural = _("Price Anomalies")
        ordering = ['-score', '-created_at']
        indexes = [
            models.Index(fields=['is_reviewed', '-score']),
            models.Index(fields=['anomaly_type', '-created_at']),
        ]

    def __str__(self):
        return f"Price Anomaly: {self.listing.title} ({self.get_anomaly_type_display()}, score: {self.score:.2f})"


# ---------------------------------------------------------------------------
# Reviews, reports, trust scores, moderation
# ---------------------------------------------------------------------------


class Review(BaseModel):
    """
    Order-based review system for multi-vendor marketplace.
    One review per order, tied to seller.
    """
    RATING_CHOICES = [(i, i) for i in range(1, 6)]  # 1-5 stars

    # OneToOne relationship with Order (one review per order)
    order = models.OneToOneField(
        'commerce.Order',
        on_delete=models.CASCADE,
        related_name='review',
        help_text="Order this review is for (required, one review per order)"
    )

    # Seller being reviewed (from order.seller)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_reviews',
        help_text="Seller being reviewed"
    )

    # Buyer writing the review (from order.buyer)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='given_reviews',
        help_text="Buyer writing the review"
    )

    # Listing from order (optional, for convenience)
    listing = models.ForeignKey(
        'listings.Listing',
        on_delete=models.SET_NULL,
        related_name='reviews',
        null=True,
        blank=True,
        help_text="Listing from order (auto-set from order items)"
    )

    rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5"
    )
    comment = models.TextField(blank=True, help_text="Review comment")

    # Seller reply to review
    seller_reply = models.TextField(blank=True, null=True, help_text="Seller's reply to this review")

    # Moderation
    is_flagged = models.BooleanField(default=False, help_text="Review flagged for moderation")
    is_hidden = models.BooleanField(default=False, help_text="Review hidden from public view")
    is_approved = models.BooleanField(default=True, help_text="Review approved by admin")

    class Meta:
        verbose_name = _("Review")
        verbose_name_plural = _("Reviews")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller', '-created_at']),
            models.Index(fields=['buyer', '-created_at']),
            models.Index(fields=['order', '-created_at']),
            models.Index(fields=['rating', '-created_at']),
            models.Index(fields=['is_hidden', 'is_approved']),
        ]

    def clean(self):
        """Validate review business rules."""
        from django.core.exceptions import ValidationError

        if not self.order:
            raise ValidationError("Order is required for review.")

        # Auto-set buyer and seller from order
        if not self.buyer_id:
            self.buyer = self.order.buyer
        if not self.seller_id:
            self.seller = self.order.seller

        # Auto-set listing from order if not set
        if not self.listing and self.order.items.exists():
            first_item = self.order.items.first()
            if first_item and first_item.listing:
                self.listing = first_item.listing

        # Validate order status and escrow (engine is source of truth)
        if self.order.status not in ('delivered', 'completed'):
            raise ValidationError(
                "Order must be delivered or completed to leave a review."
            )

        from escrow_engine.models import Transaction
        from escrow_engine.state_machine import TransactionStatus

        txn = Transaction.objects.filter(linked_order=self.order).first()
        if not txn:
            raise ValidationError("Order must have an escrow transaction.")
        if txn.status != TransactionStatus.RELEASED:
            raise ValidationError(
                "Order escrow must be released before a review can be published."
            )

        # Ensure buyer is the reviewer
        if self.buyer != self.order.buyer:
            raise ValidationError("Only the buyer of the order can leave a review.")

        # Ensure seller matches order seller
        if self.seller != self.order.seller:
            raise ValidationError("Review seller must match order seller.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Review for Order #{self.order.id} - {self.buyer.username} → {self.seller.username}: {self.rating}/5"


class ReviewMedia(BaseModel):
    """Media (images) associated with a review."""
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='media')
    file = models.ImageField(upload_to='reviews/media/')
    media_type = models.CharField(
        max_length=10,
        choices=(('image', 'Image'), ('video', 'Video')),
        default='image'
    )
    caption = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = _("Review Media")
        verbose_name_plural = _("Review Media Items")
        ordering = ['created_at']

    def __str__(self):
        return f"Media for Review #{self.review.id}"


class Report(BaseModel):
    """User reports for listings, users, or reviews."""
    REPORT_TYPES = (
        ('listing', _('Listing')),
        ('user', _('User')),
        ('review', _('Review')),
        ('message', _('Message')),
    )

    REPORT_REASONS = (
        ('spam', _('Spam')),
        ('fraud', _('Fraud')),
        ('inappropriate', _('Inappropriate Content')),
        ('misleading', _('Misleading Information')),
        ('harassment', _('Harassment')),
        ('other', _('Other')),
    )

    STATUS_CHOICES = ReportStatus.choices

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_made'
    )
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    reason = models.CharField(max_length=50, choices=REPORT_REASONS)
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )

    # Generic foreign key to reported object
    listing = models.ForeignKey(
        'listings.Listing',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports'
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports_against'
    )
    # Denormalized subject for moderation (seller / accused). Distinct-reporter counts use this field.
    subject_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trust_report_subjects',
        help_text=_('User this report is about; used for triage and automated suspension.'),
    )
    review = models.ForeignKey(
        'trust.Review',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports'
    )

    # Resolution
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_resolved'
    )
    resolution_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Report")
        verbose_name_plural = _("Reports")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['report_type', 'status']),
            models.Index(
                fields=['subject_user', 'status', '-created_at'],
                name='trust_repor_subject_stat_c_idx',
            ),
        ]

    def __str__(self):
        return f"Report #{self.id} - {self.get_report_type_display()} ({self.status})"


class TrustScore(BaseModel):
    """Calculated trust score for users (0-100)."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trust_score'
    )
    score = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Trust score from 0-100"
    )

    # Score factors
    id_verified = models.BooleanField(default=False)
    tin_verified = models.BooleanField(default=False)
    license_verified = models.BooleanField(default=False)

    # Keeping for backward compatibility
    verification_status = models.BooleanField(default=False)

    review_rating_avg = models.FloatField(default=0.0)
    transaction_success_rate = models.FloatField(default=0.0)
    violation_count = models.PositiveIntegerField(default=0)
    account_age_days = models.PositiveIntegerField(default=0)

    # Last calculation
    last_calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Trust Score")
        verbose_name_plural = _("Trust Scores")
        ordering = ['-score']

    def __str__(self):
        return f"{self.user.username}: {self.score}/100"

    def calculate_score(self):
        """Calculate trust score based on factors."""
        score = 40  # Base score

        # Identity Verification (+15)
        if self.id_verified:
            score += 15

        # TIN Verification (+15)
        if self.tin_verified:
            score += 15

        # Business License Verification (+10)
        if self.license_verified:
            score += 10

        # Review rating (0-20)
        if self.review_rating_avg > 0:
            score += min(20, self.review_rating_avg * 4)

        # Transaction success rate (0-20)
        if self.transaction_success_rate > 0:
            score += min(20, self.transaction_success_rate * 20)

        # Account age (0-10)
        if self.account_age_days > 365:
            score += 10
        elif self.account_age_days > 180:
            score += 5

        # Violations (-10 per violation, min 0)
        score -= min(50, self.violation_count * 10)

        self.score = max(0, min(100, score))
        # Sync the legacy field
        self.verification_status = self.id_verified and self.tin_verified

        return self.score


class ModerationAction(BaseModel):
    """Admin actions taken on listings, users, or reviews."""
    ACTION_TYPES = (
        ('warn', _('Warning')),
        ('suspend', _('Suspend')),
        ('ban', _('Ban')),
        ('verify', _('Verify')),
        ('unverify', _('Unverify')),
        ('delete', _('Delete')),
    )

    TARGET_TYPES = (
        ('listing', _('Listing')),
        ('user', _('User')),
        ('review', _('Review')),
    )

    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='moderation_actions'
    )
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    target_type = models.CharField(max_length=20, choices=TARGET_TYPES)

    # Generic target
    listing = models.ForeignKey(
        'listings.Listing',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='moderation_actions'
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='moderation_actions_against'
    )
    review = models.ForeignKey(
        'trust.Review',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='moderation_actions'
    )

    reason = models.TextField()
    duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration for temporary actions (suspend)"
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Moderation Action")
        verbose_name_plural = _("Moderation Actions")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_type', 'is_active']),
            models.Index(fields=['moderator', '-created_at']),
        ]

    def __str__(self):
        return f"{self.get_action_type_display()} on {self.get_target_type_display()} by {self.moderator.username}"
