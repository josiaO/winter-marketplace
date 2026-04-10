"""
escrow_engine.api.urls
-----------------------
Routes for the Developer API (X-Api-Key).
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TransactionViewSet, DisputeViewSet, RotateDeveloperAPIKeyView

router = DefaultRouter()
router.register('transactions', TransactionViewSet, basename='dev-transaction')
router.register('disputes', DisputeViewSet, basename='dev-dispute')

urlpatterns = [
    path('', include(router.urls)),
    path('keys/rotate/', RotateDeveloperAPIKeyView.as_view(), name='dev-key-rotate'),
]
