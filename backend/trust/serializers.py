from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers
from listings.models import Listing
from .models import UserVerification, ListingVerification, ReputationScore, PriceAnomaly
from .models import Review, Report, ReviewMedia, TrustScore, ModerationAction
from .reporting import resolve_subject_user

User = get_user_model()

class UserVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserVerification
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class PriceAnomalySerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceAnomaly
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class ReportSerializer(serializers.ModelSerializer):
    reporter_username = serializers.CharField(source='reporter.username', read_only=True)
    subject_username = serializers.CharField(source='subject_user.username', read_only=True, allow_null=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True, allow_null=True)

    class Meta:
        model = Report
        fields = (
            'id',
            'reporter',
            'reporter_username',
            'report_type',
            'reason',
            'description',
            'status',
            'listing',
            'listing_title',
            'reported_user',
            'subject_user',
            'subject_username',
            'review',
            'resolved_by',
            'resolution_notes',
            'resolved_at',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'reporter',
            'reporter_username',
            'status',
            'subject_user',
            'subject_username',
            'listing_title',
            'resolved_by',
            'resolution_notes',
            'resolved_at',
            'created_at',
            'updated_at',
        )


class CreateReportSerializer(serializers.ModelSerializer):
    """Validated create payload; sets subject_user and listing reported_user denormalization."""

    listing = serializers.PrimaryKeyRelatedField(
        queryset=Listing.objects.select_related('owner').all(),
        required=False,
        allow_null=True,
    )
    reported_user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )
    review = serializers.PrimaryKeyRelatedField(
        queryset=Review.objects.select_related('seller', 'buyer'),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Report
        fields = ('report_type', 'reason', 'description', 'listing', 'reported_user', 'review')

    def validate_description(self, value):
        text = (value or '').strip()
        min_len = int(getattr(settings, 'TRUST_REPORT_MIN_DESCRIPTION_LEN', 10))
        max_len = int(getattr(settings, 'TRUST_REPORT_MAX_DESCRIPTION_LEN', 5000))
        if len(text) < min_len:
            raise serializers.ValidationError(f'Description must be at least {min_len} characters.')
        if len(text) > max_len:
            raise serializers.ValidationError(f'Description must be at most {max_len} characters.')
        return text

    def validate(self, attrs):
        request = self.context['request']
        reporter = request.user
        rtype = attrs['report_type']
        listing = attrs.get('listing')
        reported_user = attrs.get('reported_user')
        review = attrs.get('review')

        if rtype == 'listing':
            if not listing:
                raise serializers.ValidationError({'listing': 'Listing is required for listing reports.'})
            if listing.owner_id and listing.owner_id == reporter.pk:
                raise serializers.ValidationError('You cannot report your own listing.')
        elif rtype == 'user':
            if not reported_user:
                raise serializers.ValidationError({'reported_user': 'User is required for user reports.'})
            if reported_user.pk == reporter.pk:
                raise serializers.ValidationError('You cannot report yourself.')
        elif rtype == 'review':
            if not review:
                raise serializers.ValidationError({'review': 'Review is required for review reports.'})
        elif rtype == 'message':
            if not reported_user:
                raise serializers.ValidationError({'reported_user': 'Reported user is required for message reports.'})
            if reported_user.pk == reporter.pk:
                raise serializers.ValidationError('You cannot report yourself.')

        dup = Report.objects.filter(reporter=reporter, status__in=('pending', 'under_review'))
        if rtype == 'listing' and listing:
            dup = dup.filter(report_type='listing', listing=listing)
        elif rtype == 'user' and reported_user:
            dup = dup.filter(report_type='user', reported_user=reported_user)
        elif rtype == 'review' and review:
            dup = dup.filter(report_type='review', review=review)
        elif rtype == 'message' and reported_user:
            dup = dup.filter(report_type='message', reported_user=reported_user)
        else:
            dup = dup.none()

        if dup.exists():
            raise serializers.ValidationError(
                'You already have an open report for this item. Please wait for moderation or contact support.'
            )

        return attrs

    def create(self, validated_data):
        reporter = self.context['request'].user
        subject = resolve_subject_user(
            report_type=validated_data['report_type'],
            listing=validated_data.get('listing'),
            reported_user=validated_data.get('reported_user'),
            review=validated_data.get('review'),
        )
        if validated_data['report_type'] == 'listing':
            listing = validated_data.get('listing')
            if listing and listing.owner_id:
                validated_data.setdefault('reported_user', listing.owner)
        return Report.objects.create(reporter=reporter, subject_user=subject, **validated_data)

class ReviewMediaSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ReviewMedia
        fields = ['id', 'file', 'file_url', 'media_type', 'caption', 'created_at']

    def get_file_url(self, obj):
        if not obj.file:
            return None
        try:
            url = obj.file.url
            if url.startswith('http://') or url.startswith('https://'):
                return url
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(url)
            return url
        except Exception:
            return None

class ReviewSerializer(serializers.ModelSerializer):
    buyer_name = serializers.CharField(source='buyer.username', read_only=True)
    buyer_email = serializers.CharField(source='buyer.email', read_only=True)
    seller_name = serializers.CharField(source='seller.username', read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True, allow_null=True)
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    verified_purchase = serializers.SerializerMethodField()

    media = ReviewMediaSerializer(many=True, read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'order', 'order_id', 'seller', 'seller_name', 'buyer', 'buyer_name', 'buyer_email',
            'listing', 'listing_title', 'rating', 'comment', 'seller_reply',
            'is_flagged', 'is_hidden', 'is_approved', 'media', 'created_at', 'updated_at',
            'verified_purchase',
        ]
        read_only_fields = [
            'id', 'order', 'seller', 'buyer', 'listing', 'is_flagged', 'is_hidden', 
            'is_approved', 'created_at', 'updated_at', 'verified_purchase',
        ]

    def get_verified_purchase(self, obj):
        return bool(getattr(obj, 'order_id', None))

class CreateReviewSerializer(serializers.ModelSerializer):
    """Serializer for creating a review from an order."""
    buyer = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Review
        fields = ['order', 'buyer', 'rating', 'comment']
    
    def validate_rating(self, value):
        """Validate rating is between 1 and 5."""
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
    
    def validate(self, attrs):
        """Validate order-based review business rules."""
        order = attrs.get('order')
        buyer = attrs.get('buyer')
        
        if not order:
            raise serializers.ValidationError("Order is required.")
        
        # Check buyer owns the order
        if order.buyer != buyer:
            raise serializers.ValidationError("You can only review orders you purchased.")
        
        if order.status not in ('delivered', 'completed'):
            raise serializers.ValidationError(
                "Order must be delivered or completed to leave a review."
            )

        from escrow_engine.models import Transaction
        from escrow_engine.state_machine import TransactionStatus

        txn = Transaction.objects.filter(linked_order=order).first()
        if not txn:
            raise serializers.ValidationError("Order must have an escrow transaction.")
        if txn.status != TransactionStatus.RELEASED:
            raise serializers.ValidationError(
                "Order escrow must be released to leave a review."
            )
        
        # Check if review already exists
        if Review.objects.filter(order=order).exists():
            raise serializers.ValidationError("A review already exists for this order.")
        
        # Auto-set seller from order
        attrs['seller'] = order.seller
        
        return attrs


class ListingVerificationSerializer(serializers.ModelSerializer):
    verified_by_username = serializers.CharField(source='verified_by.username', read_only=True)
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)
    
    class Meta:
        model = ListingVerification
        fields = [
            'id', 'listing_id', 'content_type', 'content_type_name',
            'is_verified', 'verified_by', 'verified_by_username',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_verified', 'verified_by', 'created_at', 'updated_at']
class TrustScoreSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = TrustScore
        fields = [
            'id', 'user', 'username', 'score', 
            'id_verified', 'tin_verified', 'license_verified',
            'review_rating_avg', 'transaction_success_rate', 
            'violation_count', 'account_age_days', 'last_calculated_at'
        ]
        read_only_fields = ['id', 'user', 'score', 'last_calculated_at']
