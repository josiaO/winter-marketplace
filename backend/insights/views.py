from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status, viewsets, serializers
from rest_framework.decorators import api_view, permission_classes, action
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.types import OpenApiTypes
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from collections import defaultdict

from .models import Visitor
from .tracking_service import TrackingService
from .analytics_service import AnalyticsService, SellerAnalyticsService
from listings.models import ListingLike, ListingView, Listing
from commerce.models import Order, OrderItem
from commerce.serializers import OrderSerializer
from trust.models import Review
from escrow_engine.models import Transaction as EngTxn, Payout
from escrow_engine.state_machine import TransactionStatus as _TS
from marketplace.models import SellerProfile
from accounts.permissions import IsAdmin, IsSeller
from accounts.roles import is_seller, get_user_role
from django.core.cache import cache

User = get_user_model()

class VisitorStatsAPIView(APIView):
    """View for basic visitor statistics (legacy)."""
    @extend_schema(responses={200: OpenApiTypes.OBJECT}, tags=['insights'])
    def get(self, request):
        return Response({
            "total_visitors": Visitor.objects.count(),
            "active_today": Visitor.objects.filter(
                last_seen__date=timezone.now().date()
            ).count(),
        })



class DashboardView(APIView):
    """Unified dashboard view for Admin and Sellers."""
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: OpenApiTypes.OBJECT}, tags=['insights'])
    def get(self, request):
        user = request.user
        
        if user.is_superuser or user.is_staff:
            stats = AnalyticsService.get_admin_dashboard_stats()
            return Response({
                "role": "admin",
                "kpis": {
                    "total_revenue": stats['total_revenue'],
                    "total_orders": stats['total_orders'],
                    "pending_orders": stats['pending_orders'],
                    "total_listings": stats['total_listings'],
                    "total_users": stats['total_users'],
                    "escrow": stats['escrow']
                },
                "chart_data": [], 
                "ai_insights": [
                    f"Platform revenue is at {stats['total_revenue']:,.2f} TZS.",
                    f"Currently holding {stats['escrow']['held']:,.2f} TZS in secure escrow."
                ]
            })
            
        elif hasattr(user, 'seller_profile') or user.groups.filter(name='seller').exists():
            service = SellerAnalyticsService(user.id)
            stats = service.get_stats_summary()
            
            return Response({
                "role": "seller",
                "kpis": {
                    "total_views": stats['total_views'],
                    "total_listings": stats['total_listings'],
                    "active_listings": stats['active_listings'],
                    "total_sales": stats['total_earnings']
                },
                "chart_data": [],
                "ai_insights": ["Consistently high views indicate strong product interest."]
            })
            
        return Response(status=status.HTTP_403_FORBIDDEN)


class TrackEventView(APIView):
    """Frontend endpoint for tracking user events."""
    permission_classes = [AllowAny]
    
    @extend_schema(
        request=inline_serializer("TrackEventRequest", fields={
            "event_type": serializers.CharField(),
            "metadata": serializers.DictField(required=False)
        }),
        responses={201: inline_serializer("TrackEventResponse", fields={"success": serializers.BooleanField(), "event_id": serializers.UUIDField()})}
    )
    def post(self, request):
        event_type = request.data.get('event_type')
        metadata = request.data.get('metadata', {})
        
        if not event_type:
            return Response({'error': 'event_type is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            event = TrackingService.track_from_request(
                request=request,
                event_type=event_type,
                metadata=metadata
            )
            return Response({'success': True, 'event_id': str(event.id)}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(responses={200: OpenApiTypes.OBJECT})
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_stats(request):
    """Overall منصة statistics for admin dashboard."""
    cache_key = 'admin_stats_marketplace'
    cached_stats = cache.get(cache_key)
    if cached_stats:
        return Response(cached_stats)
    
    stats = AnalyticsService.get_admin_dashboard_stats()
    
    # Map for legacy UI consistency (maintaining both snake_case and camelCase)
    legacy_stats = {
        **stats,
        'marketplace_listings': stats['marketplace_listings'],
        'marketplaceListings': stats['marketplace_listings'],
        'total_listings': stats['total_listings'],
        'totalListings': stats['total_listings'],
        'completed_orders': stats['completed_orders'],
        'completedOrders': stats['completed_orders'],
        # ... other mappings if needed, but the main ones are there
    }
    
    cache.set(cache_key, legacy_stats, 60)
    return Response(legacy_stats)


@extend_schema(responses={200: OpenApiTypes.OBJECT})
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def user_growth(request):
    """User growth data grouped by month."""
    twelve_months_ago = timezone.now() - timedelta(days=365)
    users = User.objects.filter(date_joined__gte=twelve_months_ago).values('date_joined')
    
    month_counts = defaultdict(int)
    for user in users:
        month_key = user['date_joined'].strftime('%b %Y')
        month_counts[month_key] += 1
    
    growth_data = [
        {'month': month, 'users': count}
        for month, count in sorted(month_counts.items(), key=lambda x: datetime.strptime(x[0], '%b %Y'))
    ]
    return Response(growth_data)


@extend_schema(responses={200: OpenApiTypes.OBJECT})
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def listing_growth(request):
    """Listing growth data grouped by month."""
    data = AnalyticsService.get_growth_metrics('listings')
    return Response(data)


@extend_schema(responses={200: OpenApiTypes.OBJECT})
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def revenue_growth(request):
    """Revenue growth data grouped by month."""
    data = AnalyticsService.get_growth_metrics('revenue')
    return Response(data)


@extend_schema(responses={200: OpenApiTypes.OBJECT})
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def order_growth(request):
    """Order volume growth data grouped by month."""
    data = AnalyticsService.get_growth_metrics('orders')
    return Response(data)


@extend_schema(responses={200: OpenApiTypes.OBJECT})
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def listing_stats(request):
    """Listing statistics by category and status."""
    by_category = Listing.objects.values('category__name').annotate(count=Count('id'))
    by_status = Listing.objects.values('status').annotate(count=Count('id'))
    
    return Response({
        'by_category': list(by_category),
        'by_status': list(by_status),
    })


@extend_schema(responses={200: OpenApiTypes.OBJECT})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def seller_stats_summary(request):
    """Return aggregate stats for the authenticated seller."""
    user = request.user
    has_seller_profile = hasattr(user, 'seller_profile') and user.seller_profile is not None
    
    if not (user.is_superuser or has_seller_profile):
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

    service = SellerAnalyticsService(user.id)
    stats = service.get_stats_summary()
    
    # Additional view-specific data (reviews, reviews)
    recent_reviews = Review.objects.filter(seller=user).order_by('-created_at')[:5]
    reviews_data = [{
        'id': r.id,
        'rating': r.rating,
        'comment': r.comment,
        'buyer_name': r.buyer.get_full_name() or r.buyer.username,
        'created_at': r.created_at
    } for r in recent_reviews]

    return Response({
        **stats,
        'recent_reviews': reviews_data,
        'recentReviews': reviews_data
    })

@extend_schema(responses={200: OpenApiTypes.OBJECT})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def seller_stats(request):
    """Same payload as seller-stats-summary; use this URL for marketplace seller dashboards."""
    return seller_stats_summary(request._request if hasattr(request, '_request') else request)

@extend_schema(responses={200: OpenApiTypes.OBJECT})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buyer_stats(request):
    """Get dashboard statistics for buyers."""
    user = request.user
    stats = AnalyticsService.get_buyer_stats(user)
    
    # Recent activity
    recent_orders = Order.objects.filter(buyer=user).order_by('-created_at')[:5]
    recent_orders_data = OrderSerializer(recent_orders, many=True).data

    return Response({
        'stats': stats,
        'recentOrders': recent_orders_data
    })


@extend_schema(responses={200: OpenApiTypes.OBJECT})
@api_view(['GET'])
@permission_classes([AllowAny])
def public_stats(request):
    """Curated public statistics for social proof (Homepage)."""
    stats = AnalyticsService.get_public_stats_summary()
    return Response(stats)


@extend_schema(tags=['insights'], responses={200: OpenApiTypes.OBJECT})
class SellerAnalyticsViewSet(viewsets.ViewSet):
    """ViewSet for seller analytics endpoints."""
    permission_classes = [IsAuthenticated]
    
    def _check_seller_permission(self, request):
        has_seller_profile = hasattr(request.user, 'seller_profile') and request.user.seller_profile is not None
        if not (request.user.is_superuser or has_seller_profile):
            raise PermissionDenied("Only sellers can access analytics")
    
    @action(detail=False, methods=['get'])
    def listing_performance(self, request):
        self._check_seller_permission(request)
        service = SellerAnalyticsService(request.user.id)
        listing_id = request.query_params.get('listing_id')
        days = int(request.query_params.get('days', 30))
        
        try:
            data = service.get_listing_performance(listing_id=listing_id, days=days)
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def lead_insights(self, request):
        self._check_seller_permission(request)
        service = SellerAnalyticsService(request.user.id)
        days = int(request.query_params.get('days', 30))
        
        try:
            data = service.get_lead_insights(days=days)
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def geographic(self, request):
        self._check_seller_permission(request)
        service = SellerAnalyticsService(request.user.id)
        days = int(request.query_params.get('days', 30))
        
        try:
            data = service.get_geographic_insights(days=days)
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def engagement_heatmap(self, request):
        self._check_seller_permission(request)
        service = SellerAnalyticsService(request.user.id)
        
        try:
            data = service.get_engagement_heatmap()
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def optimization_suggestions(self, request):
        self._check_seller_permission(request)
        service = SellerAnalyticsService(request.user.id)
        
        try:
            data = service.get_optimization_suggestions()
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def quick_wins(self, request):
        self._check_seller_permission(request)
        service = SellerAnalyticsService(request.user.id)
        
        try:
            data = service.get_quick_wins()
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
