from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeatureViewSet, PlanViewSet, SubscriptionPlanViewSet, SubscriptionViewSet

# Router configuration
router = DefaultRouter()
router.register(r'features', FeatureViewSet, basename='feature')
router.register(r'plans', PlanViewSet, basename='plan')
router.register(r'subscription-plans', SubscriptionPlanViewSet, basename='subscription-plan')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')

urlpatterns = [
    path("", include(router.urls)),  # Version 1 API (prefix already in backend/urls.py)
]
