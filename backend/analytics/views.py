from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from core.permissions import IsAdmin
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from .models import SellerStats, PlatformMetrics
from .serializers import (
    SellerStatsSerializer,
    PlatformMetricsSerializer,
    PlatformMetricsSummarySerializer,
)


class SellerStatsDetailView(generics.RetrieveAPIView):
    """
    GET /api/analytics/seller/me/
    Returns stats for the authenticated seller.
    """
    serializer_class = SellerStatsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        stats, _ = SellerStats.objects.get_or_create(seller=self.request.user)
        return stats


class SellerStatsRefreshView(APIView):
    """
    POST /api/analytics/seller/me/refresh/
    Triggers a full recalculation of the authenticated seller's stats.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['analytics'], request=None, responses={200: SellerStatsSerializer})
    def post(self, request):
        stats, _ = SellerStats.objects.get_or_create(seller=request.user)
        stats.calculate_stats()
        return Response(
            SellerStatsSerializer(stats).data,
            status=status.HTTP_200_OK,
        )



class PlatformMetricsViewSet(ReadOnlyModelViewSet):
    """
    GET /api/analytics/platform/          → paginated list (summary), staff/superuser only
    GET /api/analytics/platform/{date}/   → full detail for a specific date
    POST /api/analytics/platform/today/   → staff/superuser: calculate today's metrics
    """
    queryset = PlatformMetrics.objects.all().order_by('-date')
    lookup_field = 'date'
    permission_classes = [IsAdmin]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return PlatformMetrics.objects.none()
        return super().get_queryset()

    def get_serializer_class(self):
        if self.action == 'list':
            return PlatformMetricsSummarySerializer
        return PlatformMetricsSerializer

    @action(detail=False, methods=['post'], url_path='today')
    def calculate_today(self, request):
        """Admin endpoint to trigger today's metrics calculation."""
        today = timezone.now().date()
        metrics = PlatformMetrics.calculate_for_date(today)
        return Response(
            PlatformMetricsSerializer(metrics).data,
            status=status.HTTP_200_OK,
        )


# ── Admin-only: view any user's stats ──────────────────────────────────────────

class AdminSellerStatsView(generics.RetrieveAPIView):
    """
    GET /api/admin/analytics/seller/{user_id}/
    """
    serializer_class = SellerStatsSerializer
    permission_classes = [IsAdminUser]

    def get_object(self):
        stats, _ = SellerStats.objects.get_or_create(seller_id=self.kwargs['user_id'])
        return stats
