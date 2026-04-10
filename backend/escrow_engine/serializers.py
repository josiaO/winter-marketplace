"""
escrow_engine.serializers
--------------------------
DRF serializers for all escrow engine models.
"""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Transaction, TransactionLog, Payout, Dispute, DisputeEvidence, PaymentLink
from .state_machine import TransactionStatus


class TransactionLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(
        source='actor_user.username', read_only=True, allow_null=True
    )

    class Meta:
        model = TransactionLog
        fields = ['id', 'from_status', 'to_status', 'reason', 'actor_username', 'actor_label', 'created_at']


class PayoutSerializer(serializers.ModelSerializer):
    seller_username = serializers.CharField(source='seller.username', read_only=True)

    class Meta:
        model = Payout
        fields = [
            'id', 'seller_username', 'amount', 'currency',
            'status', 'payout_method', 'payout_reference', 'failure_reason',
            'created_at', 'processed_at', 'completed_at',
        ]
        read_only_fields = ['created_at', 'processed_at', 'completed_at']


class DisputeEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisputeEvidence
        fields = ['id', 'file', 'media_type', 'caption', 'created_at']


class DisputeSerializer(serializers.ModelSerializer):
    evidence = DisputeEvidenceSerializer(many=True, read_only=True)
    resolved_by_username = serializers.CharField(
        source='resolved_by.username', default=None, read_only=True
    )
    opened_by_username = serializers.CharField(
        source='opened_by.username', default=None, read_only=True
    )
    order = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Dispute
        fields = [
            'id', 'status', 'reason', 'resolution', 'resolution_type',
            'opened_by_username', 'resolved_by_username', 'resolved_at',
            'evidence', 'order', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'resolved_at']

    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_order(self, obj):
        """Link back to the marketplace order if it exists."""
        txn = obj.transaction
        if not txn or txn.source != 'marketplace' or not txn.linked_order:
            return None
        
        ord = txn.linked_order
        # Include shipment evidence from the order (seller's proof)
        shipment_evidence = []
        if ord.shipment_video:
            shipment_evidence.append({
                'file': ord.shipment_video.url,
                'media_type': 'video',
                'caption': 'Shipment Video Proof',
                'created_at': ord.shipped_at.isoformat() if ord.shipped_at else None
            })
        
        # Get OrderEvidence items (usually shipment photos)
        for ev in ord.evidence.all():
            shipment_evidence.append({
                'id': ev.id,
                'file': ev.file.url,
                'media_type': ev.media_type,
                'caption': ev.caption or 'Shipment Photo Proof',
                'created_at': ev.created_at.isoformat()
            })

        # Nested shape expected by dashboards/src/components/dashboard/admin/components/AdminDisputesTab.tsx
        return {
            'id': ord.id,
            'orderNumber': f"ORD-{str(ord.id).zfill(8)}",
            'totalAmount': str(ord.total_amount),
            'status': ord.status,
            'buyer': {
                'username': ord.buyer.username,
                'email': ord.buyer.email,
                'phone': getattr(getattr(ord.buyer, 'profile', None), 'phone_number', None) or ord.buyer_phone,
                'first_name': ord.buyer.first_name,
                'last_name': ord.buyer.last_name,
            },
            'seller': {
                'username': ord.seller.username,
                'email': ord.seller.email,
                'phone': getattr(getattr(ord.seller, 'profile', None), 'phone_number', None) or ord.seller_phone,
                'first_name': ord.seller.first_name,
                'last_name': ord.seller.last_name,
            },
            'listing': {
                'title': ord.items.first().listing.title if ord.items.exists() else 'N/A'
            },
            'shipment_evidence': shipment_evidence
        }


class TransactionSerializer(serializers.ModelSerializer):
    """Full read serializer. Used for retrieve / list."""
    logs = TransactionLogSerializer(many=True, read_only=True)
    payout = PayoutSerializer(read_only=True)
    dispute = DisputeSerializer(read_only=True)
    buyer_display = serializers.CharField(read_only=True)
    seller_display = serializers.CharField(read_only=True)
    linked_order_id = serializers.PrimaryKeyRelatedField(
        source='linked_order', read_only=True
    )

    class Meta:
        model = Transaction
        fields = [
            'id', 'reference', 'amount', 'currency', 'status', 'source',
            'buyer_display', 'seller_display',
            'buyer_phone', 'buyer_email', 'seller_phone',
            'external_reference', 'payment_method', 'gateway_reference',
            'description', 'metadata',
            'linked_order_id',
            'held_at', 'released_at', 'refunded_at',
            'created_at', 'updated_at',
            'logs', 'payout', 'dispute',
        ]
        read_only_fields = ['id', 'reference', 'created_at', 'updated_at']


class CreateTransactionSerializer(serializers.Serializer):
    """Write serializer for POST /transactions/ (API / external channel)."""
    from decimal import Decimal
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    currency = serializers.CharField(max_length=3, default='TZS')
    description = serializers.CharField(max_length=500, default='')
    metadata = serializers.DictField(required=False, default=dict)
    payment_method = serializers.CharField(max_length=50, default='selcom')
    external_reference = serializers.CharField(max_length=255, required=False, default='')
    # External-party fields
    buyer_phone = serializers.CharField(max_length=30, required=False, default='')
    buyer_email = serializers.EmailField(required=False, default='')
    seller_phone = serializers.CharField(max_length=30, required=False, default='')
    seller_email = serializers.EmailField(required=False, default='')


class InitiatePaymentSerializer(serializers.Serializer):
    """Payload for POST /transactions/{id}/pay/"""
    payment_method = serializers.CharField(max_length=50, default='selcom')
    payment_channel = serializers.CharField(max_length=50, required=False, default='')
    buyer_phone = serializers.CharField(max_length=30, required=False, default='')
    buyer_name = serializers.CharField(max_length=200, required=False, default='')
    redirect_url = serializers.URLField(required=False, default='')
    cancel_url = serializers.URLField(required=False, default='')
    idempotency_key = serializers.CharField(max_length=128, required=False, default='')


class ResolveDisputeSerializer(serializers.Serializer):
    resolution = serializers.ChoiceField(choices=['refund', 'release'])
    admin_notes = serializers.CharField(required=False, default='')


class OpenDisputeSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10)


class CreateDisputeViaViewSetSerializer(serializers.Serializer):
    """POST /disputes/ — open dispute by transaction UUID (buyer or admin only)."""
    transaction = serializers.UUIDField()
    reason = serializers.CharField(min_length=10)


# ── Payment Link Serializers ───────────────────────────────────────────────────

class PaymentLinkSerializer(serializers.ModelSerializer):
    transaction = TransactionSerializer(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    payment_url = serializers.SerializerMethodField()

    class Meta:
        model = PaymentLink
        fields = [
            'token', 'transaction', 'title', 'description',
            'expires_at', 'is_used', 'used_at', 'is_expired', 'is_valid',
            'otp_verified', 'payment_url', 'created_at',
        ]
        read_only_fields = ['token', 'is_used', 'used_at', 'created_at']

    @extend_schema_field(serializers.URLField())
    def get_payment_url(self, obj):
        return obj.get_absolute_url()


class RequestOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=30)


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=30)
    otp = serializers.CharField(max_length=8, min_length=4)


class InitiateLinkPaymentSerializer(serializers.Serializer):
    """Payload to initiate payment from a link. OTP must be verified first."""
    buyer_name = serializers.CharField(max_length=200, required=False, default='')
    redirect_url = serializers.URLField(required=False, default='')
    cancel_url = serializers.URLField(required=False, default='')
    idempotency_key = serializers.CharField(max_length=128, required=False, default='')
