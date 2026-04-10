from rest_framework import serializers
from .models import SellerStats, PlatformMetrics


class SellerStatsSerializer(serializers.ModelSerializer):
    seller_username = serializers.CharField(source='seller.username', read_only=True)
    conversion_rate = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()

    class Meta:
        model = SellerStats
        fields = [
            'id', 'seller', 'seller_username',
            # Listings
            'total_listings', 'active_listings', 'sold_listings',
            # Orders
            'total_orders', 'completed_orders', 'cancelled_orders',
            # Revenue
            'total_revenue', 'currency',
            # Reviews
            'average_rating', 'total_reviews',
            # Engagement
            'total_views', 'total_favorites',
            # Computed
            'conversion_rate', 'completion_rate',
            'last_calculated_at',
        ]
        read_only_fields = fields

    def get_conversion_rate(self, obj) -> float:
        """Percentage of views that resulted in an order."""
        if obj.total_views == 0:
            return 0.0
        return round((obj.total_orders / obj.total_views) * 100, 2)

    def get_completion_rate(self, obj) -> float:
        """Percentage of orders that were completed."""
        if obj.total_orders == 0:
            return 0.0
        return round((obj.completed_orders / obj.total_orders) * 100, 2)


class PlatformMetricsSerializer(serializers.ModelSerializer):
    user_activation_rate = serializers.SerializerMethodField()
    order_revenue_avg = serializers.SerializerMethodField()

    class Meta:
        model = PlatformMetrics
        fields = [
            'id', 'date',
            # Users
            'total_users', 'new_users_today', 'active_users_today',
            # Listings
            'total_listings', 'new_listings_today', 'active_listings',
            # Transactions
            'total_orders', 'orders_today', 'total_revenue', 'revenue_today', 'currency',
            # Engagement
            'total_views', 'views_today', 'total_searches', 'searches_today',
            # Trust
            'average_trust_score', 'verified_users',
            # Computed
            'user_activation_rate', 'order_revenue_avg',
        ]
        read_only_fields = fields

    def get_user_activation_rate(self, obj) -> float:
        """Percentage of total users active today."""
        if obj.total_users == 0:
            return 0.0
        return round((obj.active_users_today / obj.total_users) * 100, 2)

    def get_order_revenue_avg(self, obj) -> float:
        """Average revenue per order (all time)."""
        if obj.total_orders == 0:
            return 0.0
        return round(float(obj.total_revenue) / obj.total_orders, 2)


class PlatformMetricsSummarySerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views / dashboards."""
    class Meta:
        model = PlatformMetrics
        fields = ['date', 'total_users', 'active_users_today', 'orders_today',
                  'revenue_today', 'currency', 'average_trust_score']