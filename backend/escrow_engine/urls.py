"""
escrow_engine.urls
------------------
URL routes for the escrow engine API.

Mounted at: /api/v1/escrow/

Endpoints:
  POST   /api/v1/escrow/transactions/              → create new transaction
  GET    /api/v1/escrow/transactions/              → list my transactions
  GET    /api/v1/escrow/transactions/{id}/         → retrieve transaction
  POST   /api/v1/escrow/transactions/{id}/pay/     → initiate payment
  POST   /api/v1/escrow/transactions/{id}/confirm/ → confirm payment (admin)
  POST   /api/v1/escrow/transactions/{id}/release/ → release to seller (admin)
  POST   /api/v1/escrow/transactions/{id}/refund/  → refund to buyer (admin)
  POST   /api/v1/escrow/transactions/{id}/dispute/ → open dispute (buyer)
  POST   /api/v1/escrow/disputes/{id}/resolve/     → resolve dispute (admin)
  POST   /api/v1/escrow/webhooks/selcom/           → Selcom payment webhook
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    TransactionViewSet, DisputeResolveView, DisputeViewSet, SelcomWebhookView,
    CreatePaymentLinkView, PaymentLinkDetailView, RequestOTPView, VerifyOTPView, InitiateLinkPaymentView,
    EscrowHealthView, escrow_prometheus_metrics_view,
)

router = DefaultRouter()
router.register('transactions', TransactionViewSet, basename='engine-transaction')
router.register('disputes', DisputeViewSet, basename='engine-dispute')

urlpatterns = [
    # Main API (Authenticated/Public)
    path('', include(router.urls)),
    path('health/', EscrowHealthView.as_view(), name='engine-escrow-health'),
    path('metrics/', escrow_prometheus_metrics_view, name='engine-escrow-metrics'),
    path('disputes/<int:pk>/resolve/', DisputeResolveView.as_view(), name='engine-dispute-resolve'),
    path('webhooks/selcom/', SelcomWebhookView.as_view(), name='engine-webhook-selcom'),
    
    # Payment Links
    path('pay/links/', CreatePaymentLinkView.as_view(), name='engine-link-create'),
    path('pay/links/<uuid:token>/', PaymentLinkDetailView.as_view(), name='engine-link-detail'),
    path('pay/links/<uuid:token>/request-otp/', RequestOTPView.as_view(), name='engine-link-request-otp'),
    path('pay/links/<uuid:token>/verify-otp/', VerifyOTPView.as_view(), name='engine-link-verify-otp'),
    path('pay/links/<uuid:token>/pay/', InitiateLinkPaymentView.as_view(), name='engine-link-pay'),

    # Developer API (X-Api-Key)
    path('dev/', include('escrow_engine.api.urls')),
]
