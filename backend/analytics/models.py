"""
Analytics Models: SellerStats, AgentStats, PlatformMetrics
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Count, Avg
from core.models.base import BaseModel


class SellerStats(BaseModel):
    """Aggregated statistics for sellers."""
    seller = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_stats'
    )
    
    # Listings
    total_listings = models.PositiveIntegerField(default=0)
    active_listings = models.PositiveIntegerField(default=0)
    sold_listings = models.PositiveIntegerField(default=0)
    
    # Orders
    total_orders = models.PositiveIntegerField(default=0)
    completed_orders = models.PositiveIntegerField(default=0)
    cancelled_orders = models.PositiveIntegerField(default=0)
    
    # Revenue
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='TZS')
    
    # Reviews
    average_rating = models.FloatField(default=0.0)
    total_reviews = models.PositiveIntegerField(default=0)
    
    # Engagement
    total_views = models.PositiveIntegerField(default=0)
    total_favorites = models.PositiveIntegerField(default=0)
    
    # Last update
    last_calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Seller Stats")
        verbose_name_plural = _("Seller Stats")

    def __str__(self):
        return f"Stats for {self.seller.username}"

    def calculate_stats(self):
        """Recalculate stats from actual data."""
        from listings.models import Listing
        from commerce.models import Order
        from trust.models import Review
        
        # Listings
        listings = Listing.objects.filter(owner=self.seller, deleted_at__isnull=True)
        self.total_listings = listings.count()
        self.active_listings = listings.filter(status='active', is_published=True).count()
        self.sold_listings = listings.filter(status='sold').count()
        
        # Orders
        orders = Order.objects.filter(seller=self.seller)
        self.total_orders = orders.count()
        self.completed_orders = orders.filter(status='completed').count()
        self.cancelled_orders = orders.filter(status='cancelled').count()
        
        # Revenue
        revenue = orders.filter(status='completed').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        self.total_revenue = revenue
        
        # Reviews
        reviews = Review.objects.filter(reviewee=self.seller, is_approved=True)
        self.total_reviews = reviews.count()
        avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
        self.average_rating = round(avg_rating, 2)
        
        # Engagement
        self.total_views = listings.aggregate(total=Sum('view_count'))['total'] or 0
        self.total_favorites = listings.aggregate(
            total=Count('likes')
        )['total'] or 0
        
        self.save()


class PlatformMetrics(BaseModel):
    """Platform-wide aggregated metrics."""
    date = models.DateField(unique=True, db_index=True)
    
    # Users
    total_users = models.PositiveIntegerField(default=0)
    new_users_today = models.PositiveIntegerField(default=0)
    active_users_today = models.PositiveIntegerField(default=0)
    
    # Listings
    total_listings = models.PositiveIntegerField(default=0)
    new_listings_today = models.PositiveIntegerField(default=0)
    active_listings = models.PositiveIntegerField(default=0)
    
    # Transactions
    total_orders = models.PositiveIntegerField(default=0)
    orders_today = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    revenue_today = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='TZS')
    
    # Engagement
    total_views = models.PositiveIntegerField(default=0)
    views_today = models.PositiveIntegerField(default=0)
    total_searches = models.PositiveIntegerField(default=0)
    searches_today = models.PositiveIntegerField(default=0)
    
    # Trust
    average_trust_score = models.FloatField(default=0.0)
    verified_users = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Platform Metrics")
        verbose_name_plural = _("Platform Metrics")
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"Platform Metrics for {self.date}"

    @classmethod
    def calculate_for_date(cls, date):
        """Calculate metrics for a specific date."""
        from django.contrib.auth import get_user_model
        from listings.models import Listing
        from commerce.models import Order
        from escrow_engine.models import Transaction as EngTxn
        from escrow_engine.state_machine import TransactionStatus as _TS
        from trust.models import TrustScore
        
        User = get_user_model()
        
        metrics, created = cls.objects.get_or_create(date=date)
        
        # Users
        metrics.total_users = User.objects.filter(is_active=True).count()
        metrics.new_users_today = User.objects.filter(
            date_joined__date=date
        ).count()
        metrics.active_users_today = User.objects.filter(
            last_login__date=date
        ).count()
        
        # Listings
        metrics.total_listings = Listing.objects.filter(
            deleted_at__isnull=True
        ).count()
        metrics.new_listings_today = Listing.objects.filter(
            created_at__date=date
        ).count()
        metrics.active_listings = Listing.objects.filter(
            status='active',
            is_published=True,
            deleted_at__isnull=True
        ).count()
        
        # Transactions
        metrics.total_orders = Order.objects.count()
        metrics.orders_today = Order.objects.filter(created_at__date=date).count()
        
        revenue = EngTxn.objects.filter(
            status=_TS.RELEASED
        ).aggregate(total=Sum('amount'))['total'] or 0
        metrics.total_revenue = revenue
        
        revenue_today = EngTxn.objects.filter(
            status=_TS.RELEASED,
            released_at__date=date
        ).aggregate(total=Sum('amount'))['total'] or 0
        metrics.revenue_today = revenue_today
        
        # Engagement
        metrics.total_views = Listing.objects.aggregate(
            total=Sum('view_count')
        )['total'] or 0
        
        from listings.models import ListingView
        metrics.views_today = ListingView.objects.filter(
            viewed_at__date=date
        ).count()
        
        # Trust
        trust_scores = TrustScore.objects.all()
        if trust_scores.exists():
            avg_score = trust_scores.aggregate(avg=Avg('score'))['avg'] or 0
            metrics.average_trust_score = round(avg_score, 2)
        
        metrics.verified_users = TrustScore.objects.filter(
            verification_status=True
        ).count()
        
        metrics.save()
        return metrics
