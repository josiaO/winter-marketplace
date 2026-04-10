from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VisitorStatsAPIView, DashboardView, TrackEventView,
    admin_stats, user_growth, listing_growth, revenue_growth, order_growth, 
    listing_stats, public_stats, seller_stats_summary, seller_stats, buyer_stats,
    SellerAnalyticsViewSet
)

router = DefaultRouter()
router.register(r'seller', SellerAnalyticsViewSet, basename='seller-analytics')

urlpatterns = [
    path('visitor-stats/', VisitorStatsAPIView.as_view(), name='visitor-stats'),
    path('dashboard/', DashboardView.as_view(), name='dashboard-insights'),
    path('track/', TrackEventView.as_view(), name='track-event'),
    
    # Admin stats
    path('admin-stats/', admin_stats, name='admin-stats'),
    path('user-growth/', user_growth, name='user-growth'),
    path('listing-growth/', listing_growth, name='listing-growth'),
    path('revenue-growth/', revenue_growth, name='revenue-growth'),
    path('order-growth/', order_growth, name='order-growth'),
    path('listing-stats/', listing_stats, name='listing-stats'),
    path('public-stats/', public_stats, name='public-stats'),
    path('seller-stats-summary/', seller_stats_summary, name='seller-stats-summary'),
    path('seller-stats/', seller_stats, name='seller-stats'),
    path('buyer-stats/', buyer_stats, name='buyer-stats'),
    
    # Seller analytics via router
    path('', include(router.urls)),
]
