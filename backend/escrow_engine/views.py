"""
escrow_engine.views
--------------------
DRF API views for the escrow engine.

══════════════════════════════════════════════════════════════════════════════
  ✅  IN-APP CORE — READ AND WORK HERE
══════════════════════════════════════════════════════════════════════════════
These views power payments and escrow flows that occur INSIDE the SmartDalali
platform (marketplace orders, buyer/seller transactions, disputes, webhooks):

  - TransactionViewSet  — CRUD + pay / confirm / release / refund / dispute
  - DisputeResolveView  — Admin resolves a dispute (refund or release)
  - DisputeViewSet      — List, open, and respond to disputes
  - SelcomWebhookView   — Inbound Selcom payment notification (HMAC-verified)
  - EscrowHealthView    — Liveness probe for load balancers
  - escrow_prometheus_metrics_view — Prometheus scrape endpoint

All business logic lives in escrow_engine.services — views only validate
input, call services, and format responses.

══════════════════════════════════════════════════════════════════════════════
  ⏭  SKIP — PAYMENT LINKS (external, out-of-app payments)
══════════════════════════════════════════════════════════════════════════════
See the comment fence starting at "# ── BEGIN: PAYMENT LINK VIEWS ──" below.
This block implements shareable payment URLs for EXTERNAL buyers who have no
SmartDalali account. It is NOT part of the in-app marketplace escrow flow and
should be left untouched unless you are specifically working on that feature.

══════════════════════════════════════════════════════════════════════════════
  ⏭  SKIP — DEVELOPER API (escrow_engine/api/)
══════════════════════════════════════════════════════════════════════════════
The Developer API (X-Api-Key, mounted at /api/v1/escrow/dev/) exposes escrow
to third-party integrators via API keys. It lives in escrow_engine/api/ and
is completely separate from the in-app flow. Do NOT touch it unless you are
explicitly working on the external developer-facing API product.
"""
import logging
from django.conf import settings
from django.db import transaction as dj_transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied

# ── BEGIN: IMPORTS USED ONLY BY PAYMENT LINK VIEWS (external / skip) ─────────
# These symbols are imported exclusively for the Payment Link feature section
# that starts below at "BEGIN: PAYMENT LINK VIEWS". If you are working on the
# in-app escrow flow you do not need to read or modify anything related to these
# imports. They are kept here at the module level because Django / DRF resolves
# all imports on startup, but logically they belong to the skippable region.
from .throttling import EscrowPaymentLinkScopedThrottle  # Payment Links only
# ── END: IMPORTS USED ONLY BY PAYMENT LINK VIEWS ──────────────────────────────

from .models import Transaction, Dispute, PaymentLink, GatewayEvent
from .models.transaction import TransactionSource
from .serializers import (
    TransactionSerializer,
    PaymentLinkSerializer,
    CreateTransactionSerializer,
    InitiatePaymentSerializer,
    ResolveDisputeSerializer,
    OpenDisputeSerializer,
    CreateDisputeViaViewSetSerializer,
    DisputeSerializer,
    RequestOTPSerializer,
    VerifyOTPSerializer,
    InitiateLinkPaymentSerializer,
)
from .permissions import IsAdminUser, IsTransactionParty, IsTransactionBuyer
from .state_machine import PaymentConfirmationSource, TransactionStatus
import escrow_engine.services as svc
from .services import payment_link_service as pl_svc
from .services.payment import upsert_gateway_webhook_event, execute_webhook_for_stored_event
from .tasks import process_gateway_webhook_event
from . import prometheus_metrics as escrow_prom
from .providers import get_provider
from .upload_validation import validate_dispute_upload_file

from core.logging_context import log_extra

logger = logging.getLogger(__name__)


class TransactionViewSet(viewsets.ModelViewSet):
    """
    CRUD + action endpoints for the universal Transaction.

    Available to:
      - Authenticated internal users (marketplace, payment-link registered flows)
      - Developer API clients (authenticated via JWT)
    """
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated, IsTransactionParty]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if getattr(self, 'action', None) == 'pay':
            return [permissions.IsAuthenticated(), IsTransactionBuyer()]
        return super().get_permissions()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Transaction.objects.none()
        user = self.request.user
        qs = (
            Transaction.objects.select_related(
                'buyer_user', 'seller_user', 'created_by_api_key',
            )
            .prefetch_related('logs', 'dispute', 'payout', 'gateway_events')
        )
        if user.is_staff or user.is_superuser:
            return qs.order_by('-created_at')
        return qs.filter(
            Q(buyer_user=user) | Q(seller_user=user)
        ).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        """
        POST /transactions/
        Create a new escrow transaction.

        Available to API channel and external flows.
        Marketplace flows call create_transaction() from commerce checkout (OrderService).
        """
        ser = CreateTransactionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        txn = svc.create_transaction(
            amount=data['amount'],
            currency=data['currency'],
            source=TransactionSource.API,
            buyer_user=request.user,
            description=data.get('description', ''),
            metadata=data.get('metadata', {}),
            payment_method=data.get('payment_method', 'selcom'),
            external_reference=data.get('external_reference', ''),
            buyer_phone=data.get('buyer_phone', ''),
            buyer_email=data.get('buyer_email', ''),
            seller_phone=data.get('seller_phone', ''),
            seller_email=data.get('seller_email', ''),
        )
        return Response(TransactionSerializer(txn).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='pay')
    def pay(self, request, pk=None):
        """
        POST /transactions/{id}/pay/
        Initiate payment for a transaction. Returns payment_url for redirect.
        """
        txn = self.get_object()

        ser = InitiatePaymentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        if txn.status not in (TransactionStatus.CREATED, TransactionStatus.PENDING_PAYMENT):
            return Response(
                {'error': f'Transaction is in status {txn.status}. Cannot initiate payment.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = svc.initiate_payment(
            txn,
            actor=request.user,
            payment_method=data.get('payment_method', ''),
            payment_channel=data.get('payment_channel', ''),
            buyer_phone=data.get('buyer_phone', ''),
            buyer_name=data.get('buyer_name', ''),
            redirect_url=data.get('redirect_url', ''),
            cancel_url=data.get('cancel_url', ''),
            idempotency_key=data.get('idempotency_key', ''),
        )

        return Response({
            'success': result.success,
            'payment_url': result.payment_url,
            'gateway_reference': result.gateway_reference,
            'error': result.error,
            'transaction': TransactionSerializer(txn).data,
        })

    @action(detail=True, methods=['post'], url_path='confirm',
            permission_classes=[IsAdminUser])
    def confirm(self, request, pk=None):
        """
        POST /transactions/{id}/confirm/   [Admin only]
        Manually confirm payment (for cash / bank transfers).
        """
        # BUG FIX: use self.get_object() so check_object_permissions() runs
        # (IsTransactionParty object-level check was previously bypassed).
        txn = self.get_object()
        if txn.status not in (TransactionStatus.CREATED, TransactionStatus.PENDING_PAYMENT):
            return Response(
                {'error': f'Cannot confirm transaction in status {txn.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        txn = svc.confirm_payment(
            txn,
            gateway_reference=request.data.get('gateway_reference', ''),
            raw_payload=request.data.get('raw_payload') or {'admin_manual': True},
            actor=request.user,
            confirmation_source=PaymentConfirmationSource.ADMIN_MANUAL,
        )
        return Response(TransactionSerializer(txn).data)

    @action(detail=True, methods=['post'], url_path='release',
            permission_classes=[IsAdminUser])
    def release(self, request, pk=None):
        """
        POST /transactions/{id}/release/   [Admin only]
        Release escrow funds to the seller.
        """
        # BUG FIX: use self.get_object() so check_object_permissions() runs.
        txn = self.get_object()
        if txn.status != TransactionStatus.HOLD:
            return Response(
                {'error': f'Can only release funds in HOLD status. Current: {txn.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        txn = svc.release_funds(txn, actor=request.user,
                                reason=request.data.get('reason', 'Admin release'))
        return Response(TransactionSerializer(txn).data)

    @action(detail=True, methods=['post'], url_path='refund',
            permission_classes=[IsAdminUser])
    def refund(self, request, pk=None):
        """
        POST /transactions/{id}/refund/    [Admin only]
        Refund funds to the buyer.
        """
        # BUG FIX: use self.get_object() so check_object_permissions() runs.
        txn = self.get_object()
        if txn.status not in (TransactionStatus.HOLD, TransactionStatus.DISPUTED):
            return Response(
                {'error': f'Can only refund from HOLD or DISPUTED state. Current: {txn.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        txn = svc.refund_funds(txn, actor=request.user,
                               reason=request.data.get('reason', 'Admin refund'))
        return Response(TransactionSerializer(txn).data)

    @action(detail=True, methods=['post'], url_path='dispute')
    def open_dispute(self, request, pk=None):
        """
        POST /transactions/{id}/dispute/
        Open a dispute (buyer only or admin).
        """
        # BUG FIX: use self.get_object() so check_object_permissions() runs.
        # Previously get_object_or_404 bypassed IsTransactionParty entirely.
        txn = self.get_object()
        user = request.user

        # Only the buyer or admin can open a dispute
        if not (user.is_staff or user.is_superuser or txn.buyer_user == user):
            return Response(
                {'error': 'Only the buyer or an admin can open a dispute.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        ser = OpenDisputeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            dispute = svc.open_dispute(txn, opened_by=user, reason=ser.validated_data['reason'])
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DisputeSerializer(dispute).data, status=status.HTTP_201_CREATED)


class DisputeResolveView(generics.UpdateAPIView):
    """
    POST /disputes/{id}/resolve/   [Admin only]
    Resolve a dispute with 'refund' or 'release'.
    """
    queryset = Dispute.objects.all()
    serializer_class = ResolveDisputeSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ['post', 'head', 'options']

    def post(self, request, *args, **kwargs):
        dispute = get_object_or_404(Dispute, pk=kwargs['pk'])
        ser = ResolveDisputeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            dispute = svc.resolve_dispute(
                dispute,
                resolution=ser.validated_data['resolution'],
                admin_notes=ser.validated_data.get('admin_notes', ''),
                resolved_by=request.user,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DisputeSerializer(dispute).data)


class SelcomWebhookView(APIView):
    """
    POST /escrow/webhooks/selcom/   [Public — verified via HMAC]
    Receives and processes Selcom payment notifications.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=OpenApiTypes.OBJECT,
        responses={
            200: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
        description='Selcom payment webhook. Verified via Digest + Timestamp headers.',
    )
    def post(self, request, *args, **kwargs):
        provider = get_provider('selcom')
        signature = (request.headers.get('Digest') or '').strip()
        timestamp = (request.headers.get('Timestamp') or '').strip()
        payload_str = request.body.decode('utf-8')

        skip_verify = getattr(settings, 'ESCROW_WEBHOOK_INSECURE_SKIP_VERIFY', False)
        if skip_verify:
            logger.warning(
                'Selcom webhook: HMAC verification SKIPPED (ESCROW_WEBHOOK_INSECURE_SKIP_VERIFY)',
                extra=log_extra(),
            )
        else:
            if not signature or not timestamp:
                logger.error(
                    'Selcom webhook rejected: missing Digest or Timestamp header',
                    extra=log_extra(
                        has_digest=bool(signature),
                        has_timestamp=bool(timestamp),
                        content_length=len(payload_str),
                    ),
                )
                return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
            if not provider.verify_webhook_signature(payload_str, signature, timestamp):
                logger.warning(
                    'Selcom webhook: invalid HMAC signature',
                    extra=log_extra(content_length=len(payload_str)),
                )
                return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        # 2. Persist + process (async or sync — see ESCROW_WEBHOOK_ASYNC in settings)
        try:
            data = dict(request.data)
            ge, created = upsert_gateway_webhook_event('selcom', data)
            if ge.status in (
                GatewayEvent.Status.PROCESSED,
                GatewayEvent.Status.DUPLICATE,
            ):
                ref = ge.transaction.reference if ge.transaction_id else ''
                return Response(
                    {'status': 'ok', 'idempotent': True, 'reference': ref},
                    status=status.HTTP_200_OK,
                )
            if ge.status == GatewayEvent.Status.FAILED and not created:
                return Response(
                    {'status': 'ok', 'idempotent': True},
                    status=status.HTTP_200_OK,
                )

            if getattr(settings, 'ESCROW_WEBHOOK_ASYNC', False):
                dj_transaction.on_commit(
                    lambda gid=str(ge.id): process_gateway_webhook_event.delay(gid)
                )
                return Response(
                    {'status': 'accepted', 'event_id': str(ge.id)},
                    status=status.HTTP_200_OK,
                )

            txn = execute_webhook_for_stored_event(ge)
            if txn:
                logger.info("Selcom webhook processed for transaction %s", txn.reference)
                return Response({'status': 'ok', 'reference': txn.reference})

            # Event was persisted and processed but did not map to a transaction
            # (e.g. a STATUS ping or informational notification from Selcom).
            # This is a valid outcome — not an error — so return 200.
            return Response({'status': 'ok', 'matched': False})

        except Exception as exc:
            # BUG FIX: previously returned HTTP 200 here, which told Selcom the
            # event was delivered successfully and it would never retry it. Now
            # we return 500 so Selcom will retry delivery.
            logger.error(
                "Selcom webhook processing error: %s", exc, exc_info=True,
                extra=log_extra(content_length=len(payload_str)),
            )
            return Response(
                {'error': 'processing_error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EscrowHealthView(APIView):
    """
    GET /api/v1/escrow/health/ — liveness for load balancers and on-call.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        responses={
            200: OpenApiTypes.OBJECT,
            503: OpenApiTypes.OBJECT,
        },
        description='Escrow subsystem health: database, Redis, Celery worker reachability.',
    )
    def get(self, request, *args, **kwargs):
        from django.db import connection

        db_ok = True
        try:
            connection.ensure_connection()
        except Exception:
            db_ok = False

        redis_ok = True
        try:
            from django_redis import get_redis_connection

            get_redis_connection('default').ping()
        except Exception:
            redis_ok = False

        celery_ok = False
        try:
            from celery import current_app

            ping = current_app.control.inspect(timeout=0.8).ping()
            celery_ok = bool(ping)
        except Exception:
            celery_ok = False

        overall = db_ok and redis_ok
        return Response(
            {
                'status': 'ok' if overall else 'degraded',
                'database': 'up' if db_ok else 'down',
                'redis': 'up' if redis_ok else 'down',
                'celery_workers': 'up' if celery_ok else 'down_or_unreachable',
            },
            status=status.HTTP_200_OK if overall else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def escrow_prometheus_metrics_view(request):
    """
    Plain Django view for Prometheus scrape.

    BUG FIX: Previously had no access control, leaking internal operational
    metrics (transaction volumes, failure rates) to any internet caller.
    Now restricted to INTERNAL_IPS (plus loopback). Configure
    settings.INTERNAL_IPS to add your Prometheus scraper's IP(s).
    """
    client_ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', '')
    )
    allowed_ips = set(getattr(settings, 'INTERNAL_IPS', [])) | {'127.0.0.1', '::1', '::ffff:127.0.0.1'}
    if client_ip not in allowed_ips:
        logger.warning(
            'Prometheus scrape rejected from non-internal IP: %s',
            client_ip,
            extra=log_extra(),
        )
        return HttpResponse('Forbidden', status=403, content_type='text/plain')
    payload = escrow_prom.generate_latest()
    return HttpResponse(payload, content_type=escrow_prom.CONTENT_TYPE_LATEST)


# ══════════════════════════════════════════════════════════════════════════════
# ⏭  BEGIN: PAYMENT LINK VIEWS — SKIP THIS SECTION (external / out-of-app)
# ══════════════════════════════════════════════════════════════════════════════
#
# PURPOSE
# -------
# This section implements shareable, tokenised payment URLs that allow an
# EXTERNAL, unauthenticated buyer to pay a SmartDalali seller without having
# a platform account. It is NOT part of the in-app marketplace escrow flow.
#
# HOW IT WORKS
# ------------
#   1. An authenticated seller POSTs to /escrow/pay/links/ → CreatePaymentLinkView
#      creates a PaymentLink (UUID token) backed by a new escrow Transaction.
#   2. The seller shares the link URL with their external buyer.
#   3. The buyer visits /escrow/pay/links/{token}/ → PaymentLinkDetailView
#      (public) to retrieve link details.
#   4. Before paying, the buyer must verify identity via OTP:
#        POST /pay/links/{token}/request-otp/ → RequestOTPView  (sends SMS/email)
#        POST /pay/links/{token}/verify-otp/  → VerifyOTPView   (validates code)
#   5. The buyer initiates payment:
#        POST /pay/links/{token}/pay/ → InitiateLinkPaymentView → svc.initiate_payment()
#
# SERVICE LAYER
# -------------
#   escrow_engine/services/payment_link_service.py
#     - create_payment_link()  — creates Transaction + PaymentLink
#     - issue_link_otp()       — generates + delivers OTP (SMS or email)
#     - verify_link_otp()      — validates submitted OTP, marks link as verified
#
# MODEL
# -----
#   escrow_engine/models/payment_link.py :: PaymentLink
#
# URLS
# ----
#   Registered in escrow_engine/urls.py under "# Payment Links":
#     /escrow/pay/links/
#     /escrow/pay/links/{token}/
#     /escrow/pay/links/{token}/request-otp/
#     /escrow/pay/links/{token}/verify-otp/
#     /escrow/pay/links/{token}/pay/
#
# ⚠️  DO NOT EDIT unless you are specifically working on the Payment Link feature.
# ══════════════════════════════════════════════════════════════════════════════

class CreatePaymentLinkView(generics.CreateAPIView):
    """
    POST /escrow/pay/links/   [Authenticated]
    Create a new payment link backed by an escrow transaction.
    """
    serializer_class = PaymentLinkSerializer # Adjusted to use internal ser
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        ser = PaymentLinkSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        
        link = pl_svc.create_payment_link(
            amount=data['amount'],
            currency=data.get('currency', 'TZS'),
            seller_user=request.user,
            seller_phone=data.get('seller_phone', ''),
            seller_email=data.get('seller_email', ''),
            description=data.get('description', ''),
            metadata=data.get('metadata', {}),
            external_reference=data.get('external_reference', ''),
            expires_hours=int(data.get('expires_hours', 48)),
            title=data.get('title', ''),
            payment_method=data.get('payment_method', 'selcom'),
        )

        return Response(PaymentLinkSerializer(link).data, status=status.HTTP_201_CREATED)


class PaymentLinkDetailView(generics.RetrieveAPIView):
    """
    GET /escrow/pay/links/{token}/   [Public]
    """
    serializer_class = PaymentLinkSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        link = get_object_or_404(PaymentLink, token=self.kwargs['token'])
        if link.is_expired:
            raise PermissionDenied("This payment link has expired.")
        if link.is_used:
            raise PermissionDenied("This payment link has already been used.")
        return link

class RequestOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [EscrowPaymentLinkScopedThrottle]

    @extend_schema(
        request=RequestOTPSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
    )
    def post(self, request, token, *args, **kwargs):
        link = get_object_or_404(PaymentLink, token=token)
        if not link.is_valid:
            return Response({'error': 'Payment link is expired or already used.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        channel = serializer.validated_data['channel']
        destination = serializer.validated_data['destination']

        pl_svc.issue_link_otp(link, channel=channel, destination=destination)
        
        # Never log full OTP; mask destination for audit
        if channel == 'email':
            parts = destination.split('@')
            masked = f"{parts[0][0]}***@{parts[1]}" if len(parts) > 1 else '***'
        else:
            masked = destination[-4:].rjust(len(destination), '*') if len(destination) > 4 else '****'
            
        logger.info(
            "OTP issued for payment link token=%s channel=%s dest=%s",
            token, channel, masked,
        )
        return Response({'detail': f'OTP sent via {channel}. Please check your {channel}.'})


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [EscrowPaymentLinkScopedThrottle]

    @extend_schema(
        request=VerifyOTPSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
    )
    def post(self, request, token, *args, **kwargs):
        link = get_object_or_404(PaymentLink, token=token)
        if not link.is_valid:
            return Response({'error': 'Payment link is expired or already used.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        destination = serializer.validated_data['destination']
        otp = serializer.validated_data['otp']
        channel = serializer.validated_data['channel']
        
        ok = pl_svc.verify_link_otp(link, code=otp, destination=destination, channel=channel)
        if not ok:
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'detail': 'OTP verified. You may now proceed to payment.'})


class InitiateLinkPaymentView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [EscrowPaymentLinkScopedThrottle]

    @extend_schema(
        request=InitiateLinkPaymentSerializer,
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            502: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request, token, *args, **kwargs):
        link = get_object_or_404(PaymentLink.objects.select_related('transaction'), token=token)

        if not link.is_valid:
            return Response({'error': 'Payment link is expired or already used.'}, status=status.HTTP_400_BAD_REQUEST)

        if not request.user.is_authenticated and not link.otp_verified:
            return Response({'error': 'Phone verification required.'}, status=status.HTTP_403_FORBIDDEN)

        txn = link.transaction
        buyer_phone = link.buyer_phone_verified or request.data.get('buyer_phone', '')
        
        if buyer_phone and not txn.buyer_phone:
            Transaction.objects.filter(pk=txn.pk).update(buyer_phone=buyer_phone)
            txn.buyer_phone = buyer_phone

        result = svc.initiate_payment(
            txn,
            buyer_phone=buyer_phone,
            buyer_name=request.data.get('buyer_name', ''),
            redirect_url=request.data.get('redirect_url', ''),
            cancel_url=request.data.get('cancel_url', ''),
            idempotency_key=(request.data.get('idempotency_key') or '').strip(),
        )

        if result.success:
            return Response({
                'success': True,
                'payment_url': result.payment_url,
                'gateway_reference': result.gateway_reference,
                'transaction_reference': txn.reference,
            })

        return Response({'success': False, 'error': result.error}, status=status.HTTP_502_BAD_GATEWAY)


# ══════════════════════════════════════════════════════════════════════════════
# ⏭  END: PAYMENT LINK VIEWS — resume reading here for in-app escrow
# ══════════════════════════════════════════════════════════════════════════════

class DisputeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Disputes.
    Admins: all access.
    Sellers/Buyers: access to their own transaction disputes.
    """
    serializer_class = DisputeSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Dispute.objects.none()
        user = self.request.user
        # BUG FIX: added select_related for the transaction FK and its user FKs.
        # Previously only prefetch_related was used, which does NOT eliminate
        # N+1 for a direct FK — each dispute.transaction access fired a new query.
        qs = (
            Dispute.objects
            .select_related(
                'transaction',
                'transaction__buyer_user',
                'transaction__seller_user',
            )
            .prefetch_related(
                'evidence',
                'transaction__linked_order',
                'transaction__linked_order__evidence',
            )
            .order_by('-created_at')
        )
        if user.is_staff or user.is_superuser:
            return qs

        # Filter for parties involved in the transaction
        return qs.filter(
            Q(transaction__buyer_user=user) |
            Q(transaction__seller_user=user)
        )

    def create(self, request, *args, **kwargs):
        """
        POST /disputes/
        Open a dispute via service layer only (no generic model create).
        """
        ser = CreateDisputeViaViewSetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        txn = get_object_or_404(Transaction, pk=ser.validated_data['transaction'])
        user = request.user

        if not (user.is_staff or user.is_superuser or txn.buyer_user == user):
            return Response(
                {'error': 'Only the buyer or an admin can open a dispute for this transaction.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            dispute = svc.open_dispute(
                txn,
                opened_by=user,
                reason=ser.validated_data['reason'],
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DisputeSerializer(dispute).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        """Allows seller to respond to a dispute with counter-evidence."""
        dispute = self.get_object()
        user = request.user

        # Only the seller of the transaction can respond
        if dispute.transaction.seller_user != user and not (user.is_staff or user.is_superuser):
            return Response(
                {'error': 'Only the seller can respond to this dispute.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # BUG FIX: validate ALL uploaded files before acquiring the DB lock so
        # we never enter the atomic block with invalid input.
        evidence_video = request.FILES.get('evidence_video')
        if evidence_video:
            try:
                validate_dispute_upload_file(evidence_video)
            except ValueError as exc:
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        evidence_images = request.FILES.getlist('evidence_images')
        for img in evidence_images:
            try:
                validate_dispute_upload_file(img)
            except ValueError as exc:
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        notes = request.data.get('notes', '').strip()

        # BUG FIX: wrap field mutations in a single atomic block with a row lock.
        # Previously two separate dispute.save() calls (notes + video) ran without
        # a transaction, creating a partial-write window. The read-modify-write on
        # dispute.resolution also had a race condition when concurrent requests
        # both read the old value before either write committed.
        with dj_transaction.atomic():
            dispute = Dispute.objects.select_for_update().get(pk=dispute.pk)
            update_fields = []

            if notes:
                if not dispute.resolution:
                    dispute.resolution = f"Seller Response: {notes}"
                else:
                    dispute.resolution += f"\n\nSeller Response: {notes}"
                dispute.status = Dispute.Status.UNDER_REVIEW
                update_fields.extend(['resolution', 'status'])

            if evidence_video:
                dispute.evidence_video = evidence_video
                update_fields.append('evidence_video')

            if update_fields:
                update_fields.append('updated_at')
                dispute.save(update_fields=update_fields)

        # Evidence images are created outside the text-fields lock (file I/O
        # should not hold a row lock). Each image is its own row — no race.
        if evidence_images:
            from .models.dispute import DisputeEvidence
            DisputeEvidence.objects.bulk_create([
                DisputeEvidence(
                    dispute=dispute,
                    file=img,
                    media_type='image',
                    submitted_by=user,
                    caption='Seller Counter-Evidence',
                )
                for img in evidence_images
            ])

        return Response(DisputeSerializer(dispute).data)
