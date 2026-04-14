"""
escrow_engine.views
--------------------
DRF API views for:
  - Transaction CRUD  (POST /transactions/, GET /transactions/{id}/)
  - Pay               (POST /transactions/{id}/pay/)
  - Release           (POST /transactions/{id}/release/)
  - Refund            (POST /transactions/{id}/refund/)
  - Disputes          (POST /transactions/{id}/dispute/, POST /disputes/{id}/resolve/)
  - Selcom webhook    (POST /webhooks/selcom/)

No business logic lives here — all calls delegate to escrow_engine.services.
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

from .throttling import EscrowPaymentLinkScopedThrottle

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
        txn = get_object_or_404(Transaction, pk=pk)
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
        txn = get_object_or_404(Transaction, pk=pk)
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
        txn = get_object_or_404(Transaction, pk=pk)
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
        txn = get_object_or_404(Transaction, pk=pk)
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
        except Exception as exc:
            logger.error("Selcom webhook processing error: %s", exc)

        return Response({'status': 'received'})


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
    """Plain Django view for Prometheus scrape (no DRF auth)."""
    payload = escrow_prom.generate_latest()
    return HttpResponse(payload, content_type=escrow_prom.CONTENT_TYPE_LATEST)


# ── Payment Link Views ───────────────────────────────────────────────────────

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
        qs = Dispute.objects.all().order_by('-created_at').prefetch_related(
            'evidence',
            'transaction__linked_order',
            'transaction__linked_order__evidence'
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

        notes = request.data.get('notes', '').strip()
        if notes:
            # Append seller notes to the resolution field or a dedicated field if exists
            # For now, we'll prefix it set it in the resolution field if empty or log it
            if not dispute.resolution:
                dispute.resolution = f"Seller Response: {notes}"
            else:
                dispute.resolution += f"\n\nSeller Response: {notes}"
            dispute.status = Dispute.Status.UNDER_REVIEW
            dispute.save()

        evidence_video = request.FILES.get('evidence_video')
        if evidence_video:
            try:
                validate_dispute_upload_file(evidence_video)
            except ValueError as exc:
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            dispute.evidence_video = evidence_video
            dispute.save()

        evidence_images = request.FILES.getlist('evidence_images')
        for img in evidence_images:
            try:
                validate_dispute_upload_file(img)
            except ValueError as exc:
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            from .models.dispute import DisputeEvidence
            DisputeEvidence.objects.create(
                dispute=dispute,
                file=img,
                media_type='image',
                submitted_by=user,
                caption='Seller Counter-Evidence'
            )

        return Response(DisputeSerializer(dispute).data)
