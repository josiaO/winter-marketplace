from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers
from escrow_engine.models import Transaction, Dispute, DisputeEvidence, TransactionLog, PaymentLink


@extend_schema_serializer(component_name='EscrowDeveloperTransactionLog')
class TransactionLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(
        source='actor_user.username', read_only=True, allow_null=True
    )

    class Meta:
        model = TransactionLog
        fields = [
            'from_status',
            'to_status',
            'reason',
            'actor_username',
            'actor_label',
            'created_at',
        ]


@extend_schema_serializer(component_name='EscrowDeveloperTransaction')
class TransactionSerializer(serializers.ModelSerializer):
    logs = TransactionLogSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id', 'reference', 'amount', 'currency', 'status', 'status_display',
            'source', 'source_display', 'buyer_user', 'seller_user',
            'buyer_phone', 'buyer_email', 'seller_phone', 'seller_email',
            'external_reference', 'payment_method', 'gateway_reference',
            'description', 'metadata', 'created_at', 'updated_at',
            'held_at', 'released_at', 'refunded_at', 'logs',
        ]
        read_only_fields = ['id', 'reference', 'status', 'created_at', 'updated_at', 'logs']


@extend_schema_serializer(component_name='EscrowDeveloperCreateTransaction')
class CreateTransactionSerializer(serializers.ModelSerializer):
    """Specifically for creating transactions via Developer API."""
    class Meta:
        model = Transaction
        fields = [
            'amount', 'currency', 'source', 'buyer_phone', 'buyer_email',
            'seller_phone', 'seller_email', 'external_reference',
            'payment_method', 'description', 'metadata'
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


@extend_schema_serializer(component_name='EscrowDeveloperDisputeEvidence')
class DisputeEvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisputeEvidence
        fields = ['id', 'file', 'media_type', 'caption', 'submitted_by', 'created_at']


@extend_schema_serializer(component_name='EscrowDeveloperDispute')
class DisputeSerializer(serializers.ModelSerializer):
    evidence = DisputeEvidenceSerializer(many=True, read_only=True)

    class Meta:
        model = Dispute
        fields = [
            'id', 'transaction', 'opened_by', 'reason', 'status',
            'resolution', 'resolution_type', 'resolved_by', 'resolved_at',
            'evidence', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'resolved_at', 'evidence']


@extend_schema_serializer(component_name='EscrowDeveloperPaymentLink')
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
