"""
escrow_engine.urls
------------------
URL routes for the escrow engine API.

Mounted at: /api/v1/escrow/

══════════════════════════════════════════════════════════════════════════════
  ✅  IN-APP CORE ENDPOINTS — work here
══════════════════════════════════════════════════════════════════════════════
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

══════════════════════════════════════════════════════════════════════════════
  ⏭  SKIP — Payment Link endpoints (external / out-of-app)
══════════════════════════════════════════════════════════════════════════════
  POST   /api/v1/escrow/pay/links/
  GET    /api/v1/escrow/pay/links/{token}/
  POST   /api/v1/escrow/pay/links/{token}/request-otp/
  POST   /api/v1/escrow/pay/links/{token}/verify-otp/
  POST   /api/v1/escrow/pay/links/{token}/pay/

══════════════════════════════════════════════════════════════════════════════
  ⏭  SKIP — Developer API endpoints (X-Api-Key / external integrators)
══════════════════════════════════════════════════════════════════════════════
  ALL    /api/v1/escrow/dev/  → escrow_engine/api/  (separate package)
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
    
    # ─────────────────────────────────────────────────────────────────────────
    # ⏭  BEGIN: PAYMENT LINK URLS — SKIP (external out-of-app feature)
    # These routes serve CreatePaymentLinkView, PaymentLinkDetailView,
    # RequestOTPView, VerifyOTPView, and InitiateLinkPaymentView.
    # They power shareable payment URLs for unauthenticated external buyers.
    # Source: escrow_engine/views.py — "BEGIN: PAYMENT LINK VIEWS" section
    # ─────────────────────────────────────────────────────────────────────────
    path('pay/links/', CreatePaymentLinkView.as_view(), name='engine-link-create'),
    path('pay/links/<uuid:token>/', PaymentLinkDetailView.as_view(), name='engine-link-detail'),
    path('pay/links/<uuid:token>/request-otp/', RequestOTPView.as_view(), name='engine-link-request-otp'),
    path('pay/links/<uuid:token>/verify-otp/', VerifyOTPView.as_view(), name='engine-link-verify-otp'),
    path('pay/links/<uuid:token>/pay/', InitiateLinkPaymentView.as_view(), name='engine-link-pay'),

    # ─────────────────────────────────────────────────────────────────────────
    # ⏭  END: PAYMENT LINK URLS
    # ─────────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────────
    # ⏭  BEGIN: DEVELOPER API URLS — SKIP (external X-Api-Key product)
    # All routes under /dev/ are handled by escrow_engine/api/.
    # That package has its own views, serializers, permissions, throttling,
    # and authentication (APIKeyAuthentication). It is a self-contained product
    # for third-party developers and has NOTHING to do with the in-app flow.
    # Source: escrow_engine/api/urls.py + escrow_engine/api/views.py
    # ─────────────────────────────────────────────────────────────────────────
    path('dev/', include('escrow_engine.api.urls')),
    # ─────────────────────────────────────────────────────────────────────────
    # ⏭  END: DEVELOPER API URLS
    # ─────────────────────────────────────────────────────────────────────────
]
