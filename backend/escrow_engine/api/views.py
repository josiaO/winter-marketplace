"""
escrow_engine.api.views
-----------------------
⏭  SKIP THIS FILE — Developer API (external X-Api-Key product)
══════════════════════════════════════════════════════════════════════════════

This file is NOT part of the in-app SmartDalali escrow flow.

PURPOSE
-------
This package (escrow_engine/api/) implements a standalone Developer API that
allows THIRD-PARTY INTEGRATORS to interact with the escrow engine using a
static X-Api-Key header. It is a separate product from the marketplace itself.

WHAT IT DOES
------------
  - TransactionViewSet   — create/list/pay/release/refund txns via API key
  - DisputeViewSet       — open/list disputes for API-key-owned transactions
  - RotateDeveloperAPIKeyView — rotate an API key and receive a new secret

AUTH
----
  Authentication : escrow_engine.api.authentication.APIKeyAuthentication
  Permissions   : escrow_engine.api.permissions.HasEscrowAPIKey / EscrowAPIKeyScopes
  Throttling    : escrow_engine.api.throttling.EscrowDeveloperAPIKeyThrottle

URLS
----
  Mounted under: /api/v1/escrow/dev/
    /dev/transactions/
    /dev/transactions/{reference}/pay/
    /dev/transactions/{reference}/release/
    /dev/transactions/{reference}/refund/
    /dev/disputes/
    /dev/keys/rotate/

⚠️  DO NOT EDIT unless you are working specifically on the Developer API product.
    To work on in-app escrow: go to escrow_engine/views.py instead.
══════════════════════════════════════════════════════════════════════════════
"""
import secrets

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from escrow_engine.models import Transaction, Dispute, APIKey
from escrow_engine.models.api_key import hash_api_key
from escrow_engine.api.authentication import APIKeyAuthentication
from escrow_engine.api.permissions import HasEscrowAPIKey, EscrowAPIKeyScopes
from escrow_engine.api.throttling import EscrowDeveloperAPIKeyThrottle
from escrow_engine.api.serializers import (
    TransactionSerializer,
    CreateTransactionSerializer,
    DisputeSerializer,
)
from escrow_engine.services.transaction import create_transaction
from escrow_engine.services.payment import initiate_payment
from escrow_engine.services.escrow import release_funds, refund_funds, open_dispute


def _api_key_actor_label(key: APIKey) -> str:
    return f'APIKey:{key.name}'


class TransactionViewSet(viewsets.ModelViewSet):
    """
    Developer API for managing universal escrow transactions.
    Requires X-Api-Key with appropriate scopes; only sees txns created with that key.
    """
    serializer_class = TransactionSerializer
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasEscrowAPIKey, EscrowAPIKeyScopes]
    throttle_classes = [EscrowDeveloperAPIKeyThrottle]
    lookup_field = 'reference'

    def get_queryset(self):
        key = self.request.auth
        return Transaction.objects.filter(created_by_api_key=key).order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateTransactionSerializer
        return TransactionSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        txn = create_transaction(
            **serializer.validated_data,
            source='api',
            created_by_api_key=request.auth,
        )

        return Response(
            TransactionSerializer(txn).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def pay(self, request, reference=None):
        """Initiate payment for this transaction."""
        txn = self.get_object()

        result = initiate_payment(
            txn,
            payment_method=request.data.get('payment_method', 'selcom'),
            buyer_phone=request.data.get('buyer_phone', ''),
            buyer_name=request.data.get('buyer_name', ''),
            idempotency_key=(request.data.get('idempotency_key') or '').strip(),
        )

        if result.success:
            return Response({
                'success': True,
                'payment_url': result.payment_url,
                'gateway_reference': result.gateway_reference,
            })

        return Response({
            'success': False,
            'error': result.error
        }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def release(self, request, reference=None):
        """Manually release funds."""
        txn = self.get_object()
        label = _api_key_actor_label(request.auth)

        try:
            release_funds(
                txn,
                actor=None,
                actor_label=label,
                reason=request.data.get('reason', 'API Release'),
            )
            return Response({'status': 'released'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def refund(self, request, reference=None):
        """Manually refund funds."""
        txn = self.get_object()
        label = _api_key_actor_label(request.auth)

        try:
            refund_funds(
                txn,
                actor=None,
                actor_label=label,
                reason=request.data.get('reason', 'API Refund'),
            )
            return Response({'status': 'refunded'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DisputeViewSet(viewsets.ModelViewSet):
    """
    Developer API for disputes on API-key-owned transactions only.
    """
    serializer_class = DisputeSerializer
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasEscrowAPIKey, EscrowAPIKeyScopes]
    throttle_classes = [EscrowDeveloperAPIKeyThrottle]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        key = self.request.auth
        return Dispute.objects.filter(
            transaction__created_by_api_key=key
        ).order_by('-created_at').select_related('transaction', 'opened_by')

    def create(self, request, *args, **kwargs):
        txn_ref = request.data.get('transaction_reference')
        reason = (request.data.get('reason') or '').strip()
        if len(reason) < 10:
            return Response(
                {'error': 'reason must be at least 10 characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        key = request.auth
        txn = get_object_or_404(
            Transaction.objects.filter(created_by_api_key=key),
            reference=txn_ref,
        )
        label = _api_key_actor_label(key)

        try:
            dispute = open_dispute(
                transaction=txn,
                opened_by=None,
                actor_label=label,
                reason=reason,
            )
            return Response(
                DisputeSerializer(dispute).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RotateDeveloperAPIKeyView(APIView):
    """
    POST /api/v1/escrow/dev/keys/rotate/
    Authenticate with current X-Api-Key; receive a new secret once, old key deactivated.
    """

    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasEscrowAPIKey]

    @extend_schema(
        request=None,
        responses={
            201: inline_serializer(
                name='RotateDeveloperAPIKeyResponse',
                fields={
                    'secret': drf_serializers.CharField(),
                    'key_id': drf_serializers.IntegerField(),
                    'name': drf_serializers.CharField(),
                    'message': drf_serializers.CharField(),
                },
            ),
            403: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request):
        old = request.auth
        if old.expires_at and old.expires_at < timezone.now():
            return Response({'error': 'API key has expired.'}, status=status.HTTP_403_FORBIDDEN)
        raw = secrets.token_urlsafe(32)
        new_key = APIKey.objects.create(
            name=f'{old.name} (rotated via API)',
            key_hash=hash_api_key(raw),
            is_active=True,
            scopes=list(old.scopes or []),
            ip_allowlist=list(old.ip_allowlist or []),
            rate_limit_per_minute=old.rate_limit_per_minute,
            expires_at=old.expires_at,
        )
        old.is_active = False
        old.save(update_fields=['is_active', 'updated_at'])
        return Response(
            {
                'secret': raw,
                'key_id': new_key.pk,
                'name': new_key.name,
                'message': 'Store the secret securely; it will not be shown again.',
            },
            status=status.HTTP_201_CREATED,
        )
