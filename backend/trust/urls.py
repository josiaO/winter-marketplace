from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserVerificationViewSet, PriceAnomalyViewSet, ReportViewSet, 
    ReviewViewSet, ListingVerificationViewSet, TrustScoreViewSet
)

router = DefaultRouter()
router.register(r'verifications', UserVerificationViewSet, basename='verification')
router.register(r'trust-scores', TrustScoreViewSet, basename='trust-score')
router.register(r'listing-verifications', ListingVerificationViewSet, basename='listing-verification')
router.register(r'anomalies', PriceAnomalyViewSet, basename='anomaly')
router.register(r'reports', ReportViewSet, basename='report')
router.register(r'reviews', ReviewViewSet, basename='review')

urlpatterns = [
    path('', include(router.urls)),
]
