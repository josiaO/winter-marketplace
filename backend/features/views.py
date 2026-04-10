from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import Plan, Feature, SubscriptionPlan, Subscription
from .serializers import PlanSerializer, FeatureSerializer, SubscriptionPlanSerializer, SubscriptionSerializer
from core.drf_utils import viewset_mapped_action

class FeatureViewSet(viewsets.ModelViewSet):
    """Full CRUD for features"""
    queryset = Feature.objects.all()
    serializer_class = FeatureSerializer
    permission_classes = [permissions.AllowAny]  # Public read, admin write

    def get_authenticators(self):
        if viewset_mapped_action(self) in ('list', 'retrieve'):
            return []
        return super().get_authenticators()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

class PlanViewSet(viewsets.ModelViewSet):
    """Full CRUD for plans with nested features"""
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]

    def get_authenticators(self):
        if viewset_mapped_action(self) in ('list', 'retrieve'):
            return []
        return super().get_authenticators()
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """Legacy subscription plans for payment system"""
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SubscriptionPlan.objects.none()
        if self.request.user.is_superuser:
            return SubscriptionPlan.objects.all()
        return SubscriptionPlan.objects.filter(is_active=True)
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for user subscriptions.
    Provides 'current' endpoint for the active user's subscription.
    """
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Subscription.objects.none()
        return Subscription.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def current(self, request):
        """
        Get the current active subscription for the authenticated user.
        If no subscription exists, return a default/free tier structure or 404.
        """
        now = timezone.now()
        subscription = Subscription.objects.filter(
            user=request.user,
            is_active=True,
            end_date__gt=now
        ).first()

        if subscription:
            serializer = self.get_serializer(subscription)
            return Response(serializer.data)
        
        # Fallback: Check if there's a default free plan
        # For now, we return 404 to match existing frontend logic which handles 404 as "no subscription"
        return Response(
            {"detail": "No active subscription found."}, 
            status=status.HTTP_404_NOT_FOUND
        )
