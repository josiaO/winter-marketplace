import uuid
from django.db import models

class DailyMetric(models.Model):
    """Legacy simple daily counters; prefer analytics.PlatformMetrics for platform rollups."""
    date = models.DateField()
    views = models.PositiveIntegerField(default=0)
    leads = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"Metrics for {self.date}"


class Visitor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(max_length=100, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    visit_count = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"Visitor {self.session_key}"


class Event(models.Model):
    """Tracks user events for behavioral analytics."""
    
    EVENT_TYPES = [
        ('page_view', 'Page View'),
        ('listing_search', 'Listing Search'),
        ('listing_view', 'Listing Detail View'),
        ('listing_like', 'Listing Liked/Saved'),
        ('account_register', 'Account Registration'),
        ('seller_contact', 'Seller Contact'),
        ('order_request', 'Order Request'),
        ('message_sent', 'Message Sent'),
    ]
    
    DEVICE_TYPES = [
        ('mobile', 'Mobile'),
        ('tablet', 'Tablet'),
        ('desktop', 'Desktop'),
        ('other', 'Other'),
        ('unknown', 'Unknown'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_id = models.CharField(max_length=100, db_index=True)
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events'
    )
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Technical metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES, default='unknown')
    referrer = models.URLField(max_length=500, blank=True)
    
    # Geographic data (can be enriched later with GeoIP)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_id', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['event_type', 'created_at']),
        ]
    
    def __str__(self):
        user_id = self.user_id if self.user else 'anonymous'
        return f"{self.event_type} by {user_id} at {self.created_at}"

class ListingEngagement(models.Model):
    """
    Aggregated engagement metrics per listing.
    """
    listing = models.OneToOneField(
        'listings.Listing',
        on_delete=models.CASCADE,
        related_name='engagement_metrics'
    )
    total_shares = models.PositiveIntegerField(default=0)
    total_contact_attempts = models.PositiveIntegerField(default=0)
    total_likes = models.PositiveIntegerField(default=0)
    last_engagement = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Engagement metrics for {self.listing.title}"
    
    def update_likes_count(self):
        """Update total likes from listings.ListingLike model"""
        from listings.models import ListingLike
        self.total_likes = ListingLike.objects.filter(listing=self.listing).count()
        self.save(update_fields=['total_likes', 'updated_at'])


class SellerLeadMetrics(models.Model):
    """
    Daily aggregated lead metrics per seller for performance tracking.
    """
    seller = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='lead_metrics'
    )
    date = models.DateField(db_index=True)
    new_messages = models.PositiveIntegerField(default=0)
    conversations_started = models.PositiveIntegerField(default=0)
    response_time_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Average response time in minutes"
    )
    total_responses = models.PositiveIntegerField(
        default=0,
        help_text="Number of responses sent this day"
    )
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['seller', 'date']
        indexes = [
            models.Index(fields=['seller', '-date']),
        ]
    
    def __str__(self):
        return f"Lead metrics for {self.seller.username} on {self.date}"


class GeographicInsight(models.Model):
    """
    Track location-based search and view patterns.
    """
    location_name = models.CharField(max_length=100, db_index=True)
    seller = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='geographic_insights',
        null=True,
        blank=True,
        help_text="Seller whose items are being viewed (null for global)"
    )
    search_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    date = models.DateField(db_index=True)
    
    class Meta:
        ordering = ['-date', '-view_count']
        unique_together = ['location_name', 'seller', 'date']
        indexes = [
            models.Index(fields=['seller', '-date']),
            models.Index(fields=['location_name', '-date']),
        ]
    
    def __str__(self):
        seller_name = self.seller.username if self.seller else 'Global'
        return f"{self.location_name} - {seller_name} ({self.date})"


class WeeklyEngagementPattern(models.Model):
    """
    Track weekly engagement patterns for sellers (for heatmap visualization).
    """
    DAYS_OF_WEEK = (
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    )
    
    ACTIVITY_LEVELS = (
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Very High', 'Very High'),
    )
    
    seller = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='engagement_patterns'
    )
    week_start_date = models.DateField(db_index=True)
    day_of_week = models.CharField(max_length=10, choices=DAYS_OF_WEEK)
    activity_level = models.CharField(max_length=10, choices=ACTIVITY_LEVELS, default='Low')
    total_views = models.PositiveIntegerField(default=0)
    total_inquiries = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['week_start_date', 'day_of_week']
        unique_together = ['seller', 'week_start_date', 'day_of_week']
        indexes = [
            models.Index(fields=['seller', '-week_start_date']),
        ]
    
    def __str__(self):
        return f"{self.seller.username} - {self.day_of_week} (Week of {self.week_start_date})"
    
    def calculate_activity_level(self):
        """Calculate activity level based on views and inquiries"""
        total_activity = self.total_views + (self.total_inquiries * 10)
        
        if total_activity >= 100:
            self.activity_level = 'Very High'
        elif total_activity >= 50:
            self.activity_level = 'High'
        elif total_activity >= 20:
            self.activity_level = 'Medium'
        else:
            self.activity_level = 'Low'
        
        self.save(update_fields=['activity_level'])
