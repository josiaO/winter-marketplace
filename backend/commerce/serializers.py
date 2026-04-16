"""
Commerce Serializers: Order, OrderItem, Cart, Delivery, StockReservation
"""
from django.conf import settings
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderEvidence,
    Delivery,
    StockReservation,
    Wishlist,
    WishlistItem,
    SellerWithdrawalRequest,
    ListingOffer,
)
from listings.serializers import ListingSerializer
from accounts.serializers import UserSerializer


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for cart items."""
    listing = ListingSerializer(read_only=True)
    listing_id = serializers.IntegerField(write_only=True)
    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = CartItem
        fields = [
            'id', 'listing', 'listing_id', 'quantity',
            'price_at_time', 'subtotal', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'price_at_time', 'created_at', 'updated_at']


class CartSerializer(serializers.ModelSerializer):
    """Serializer for shopping cart."""
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = ['id', 'user', 'items', 'total', 'item_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    @extend_schema_field(serializers.IntegerField())
    def get_item_count(self, obj):
        return obj.items.count()


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order items."""
    listing = ListingSerializer(read_only=True)
    listing_id = serializers.IntegerField(write_only=True)
    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'order', 'listing', 'listing_id', 'quantity',
            'price_at_time', 'subtotal', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'order', 'price_at_time', 'created_at', 'updated_at']


class OrderEvidenceSerializer(serializers.ModelSerializer):
    """Serializer for order evidence files."""
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = OrderEvidence
        fields = ['id', 'file', 'file_url', 'media_type', 'caption', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None


def _order_items_cached(order):
    """Use prefetched items when present to avoid per-order item queries."""
    cache = getattr(order, '_prefetched_objects_cache', None)
    if cache and 'items' in cache:
        return cache['items']
    return None


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for orders."""
    buyer = UserSerializer(read_only=True)
    seller = UserSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    seller_payout_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    escrow = serializers.SerializerMethodField()
    dispute = serializers.SerializerMethodField()
    buyer_details = serializers.SerializerMethodField()
    buyer_location = serializers.SerializerMethodField()
    seller_details = serializers.SerializerMethodField()
    orderNumber = serializers.SerializerMethodField()
    listing = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    unitPrice = serializers.SerializerMethodField()
    totalAmount = serializers.DecimalField(source='total_amount', max_digits=12, decimal_places=2, read_only=True)
    platformFee = serializers.DecimalField(source='platform_fee', max_digits=12, decimal_places=2, read_only=True)
    sellerPayout = serializers.DecimalField(source='seller_payout_amount', max_digits=12, decimal_places=2, read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    shippedAt = serializers.DateTimeField(source='shipped_at', read_only=True)
    deliveredAt = serializers.DateTimeField(source='delivered_at', read_only=True)
    arrivedAt = serializers.DateTimeField(source='arrived_at', read_only=True)
    buyerId = serializers.IntegerField(source='buyer.id', read_only=True)
    sellerId = serializers.IntegerField(source='seller.id', read_only=True)
    listingId = serializers.SerializerMethodField()
    status = serializers.CharField() # Ensure status is returned as string
    review = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'orderNumber', 'buyer', 'seller', 'status',
            'subtotal', 'shipping_cost', 'platform_fee', 'total_amount', 'currency',
            'shipping_address', 'shipping_method', 'tracking_number', 'arrival_location',
            'buyer_notes', 'seller_notes',
            'seller_payout_amount', 'escrow', 'dispute',
            'buyer_details', 'buyer_location', 'seller_details',
            'confirmed_at', 'processing_at', 'shipped_at',
            'delivered_at', 'arrived_at', 'completed_at', 'cancelled_at',
            'items', 'listing', 'quantity', 'unitPrice',
            'totalAmount', 'platformFee', 'sellerPayout', 
            'createdAt', 'updatedAt', 'shippedAt', 'deliveredAt', 'arrivedAt',
            'buyerId', 'sellerId', 'listingId',
            'shipment_video', 'shipment_images_count', 'evidence',
            'review',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'orderNumber', 'buyer', 'seller', 'total_amount',
            'seller_payout_amount', 'escrow', 'buyer_details', 'buyer_location', 'seller_details',
            'listing', 'quantity', 'unitPrice',
            'confirmed_at', 'processing_at', 'shipped_at',
            'delivered_at', 'arrived_at', 'completed_at', 'cancelled_at',
            'created_at', 'updated_at'
        ]
    
    def to_representation(self, instance):
        if getattr(settings, 'ESCROW_PARANOID_MODE', False):
            from commerce.services.invariants import maybe_assert_order_transaction_consistency

            maybe_assert_order_transaction_consistency(instance)
        return super().to_representation(instance)

    @extend_schema_field(serializers.CharField())
    def get_orderNumber(self, obj):
        """Generate order number from ID."""
        return f"ORD-{str(obj.id).zfill(8)}"

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_listingId(self, obj):
        """Get ID of the first listing."""
        cached = _order_items_cached(obj)
        items_iter = cached if cached is not None else obj.items.all()
        first_item = next(iter(items_iter), None)
        if first_item and first_item.listing_id:
            return first_item.listing_id
        return None
    
    @extend_schema_field(ListingSerializer(allow_null=True))
    def get_listing(self, obj):
        """Get first listing from order items for backward compatibility."""
        cached = _order_items_cached(obj)
        items_iter = cached if cached is not None else obj.items.all()
        first_item = next(iter(items_iter), None)
        if first_item and first_item.listing:
            return ListingSerializer(first_item.listing, context=self.context).data
        return None
    
    @extend_schema_field(serializers.IntegerField())
    def get_quantity(self, obj):
        """Get total quantity from all order items."""
        cached = _order_items_cached(obj)
        items_iter = cached if cached is not None else obj.items.all()
        return sum(item.quantity for item in items_iter)
    
    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_unitPrice(self, obj):
        """Get unit price from first item for backward compatibility."""
        cached = _order_items_cached(obj)
        items_iter = cached if cached is not None else obj.items.all()
        first_item = next(iter(items_iter), None)
        if first_item:
            return float(first_item.price_at_time)
        return None
    
    @extend_schema_field(OrderEvidenceSerializer(many=True))
    def get_evidence(self, obj):
        """Get all evidence for this order."""
        return OrderEvidenceSerializer(obj.evidence.all(), many=True).data
    
    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_buyer_details(self, obj):
        """Get comprehensive buyer information."""
        if not obj.buyer:
            return None
        
        # Use prefetched profile if available
        profile = getattr(obj.buyer, 'profile', None)
        
        details = {
            'id': obj.buyer.id,
            'username': obj.buyer.username,
            'email': obj.buyer.email,
            'first_name': obj.buyer.first_name,
            'last_name': obj.buyer.last_name,
            'full_name': obj.buyer.get_full_name() or obj.buyer.username,
        }
        
        if profile:
            details.update({
                'phone_number': profile.phone_number,
                'address': profile.address,
                'profile_image': profile.image.url if profile.image else None,
            })
            
        return details
    
    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_buyer_location(self, obj):
        """Get buyer location information from shipping address or profile."""
        location_info = {}
        
        # Get shipping address from order
        if obj.shipping_address:
            location_info['shipping_address'] = obj.shipping_address
        
        # Get address from buyer profile
        try:
            profile = getattr(obj.buyer, 'profile', None)
            if profile and profile.address:
                location_info['profile_address'] = profile.address
        except Exception:
            pass
        
        return location_info if location_info else None
    
    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_seller_details(self, obj):
        """Get comprehensive seller information."""
        if not obj.seller:
            return None
            
        profile = getattr(obj.seller, 'profile', None)
        seller_profile = getattr(obj.seller, 'seller_profile', None)
        
        details = {
            'id': obj.seller.id,
            'username': obj.seller.username,
            'email': obj.seller.email,
            'first_name': obj.seller.first_name,
            'last_name': obj.seller.last_name,
            'full_name': obj.seller.get_full_name() or obj.seller.username,
        }
        
        if profile:
            details.update({
                'phone_number': profile.phone_number,
                'address': profile.address,
                'profile_image': profile.image.url if profile.image else None,
            })
            
        if seller_profile:
            details['business_name'] = seller_profile.business_name
            
        return details
    
    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_escrow(self, obj):
        """Get the linked engine transaction status."""
        # obj.engine_transaction is a OneToOneField from escrow_engine.Transaction
        # Check if it was prefetched or already fetched
        txn = getattr(obj, 'engine_transaction', None)
        if txn:
            return {
                'id': str(txn.id),
                'reference': txn.reference,
                'status': txn.status,
                'amount': str(txn.amount),
                'currency': txn.currency,
                'dispute_resolved_by': (
                    txn.dispute_resolved_by.id if txn.dispute_resolved_by else None
                ),
            }
        return None
    
    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_dispute(self, obj):
        """Get the linked engine dispute details."""
        dispute = getattr(obj, 'engine_dispute', None)
        if not dispute and hasattr(obj, 'engine_transaction'):
            dispute = getattr(obj.engine_transaction, 'dispute', None)
        
        if not dispute:
            return None
            
        return {
            'id': dispute.id,
            'status': dispute.status,
            'reason': dispute.reason,
            'evidence_images': [e.file.url for e in dispute.evidence.filter(media_type='image')],
            'evidence_video': dispute.evidence_video.url if dispute.evidence_video else None,
            'resolution': dispute.resolution,
            'admin_notes': dispute.reason, # Using reason as info
            'created_at': dispute.created_at,
        }

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_review(self, obj):
        """Get the linked review for this order."""
        review = getattr(obj, 'review', None)
        if not review:
            return None
            
        from trust.serializers import ReviewSerializer
        return ReviewSerializer(review, context=self.context).data


# Note: EscrowTransactionSerializer and PayoutSerializer have been removed 
# and are now handled by the escrow_engine app.


class DeliverySerializer(serializers.ModelSerializer):

    """Serializer for delivery/shipping tracking."""
    order = OrderSerializer(read_only=True)
    
    class Meta:
        model = Delivery
        fields = [
            'id', 'order', 'method', 'status',
            'recipient_name', 'recipient_phone',
            'address_line1', 'address_line2', 'city', 'region', 'postal_code', 'country',
            'tracking_number', 'carrier', 'tracking_url',
            'shipped_at', 'estimated_delivery', 'delivered_at',
            'delivery_notes', 'signature_required',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order', 'shipped_at', 'delivered_at',
            'created_at', 'updated_at'
        ]


class StockReservationSerializer(serializers.ModelSerializer):
    """Serializer for stock reservations."""
    listing = ListingSerializer(read_only=True)
    order = OrderSerializer(read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = StockReservation
        fields = [
            'id', 'listing', 'order', 'cart_item',
            'quantity', 'status', 'expires_at', 'is_expired',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'listing', 'order', 'cart_item',
            'status', 'created_at', 'updated_at'
        ]
    
    def get_is_expired(self, obj):
        return obj.is_expired()


class WishlistItemSerializer(serializers.ModelSerializer):
    """Serializer for wishlist items."""
    listing = ListingSerializer(read_only=True)
    listing_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = WishlistItem
        fields = ['id', 'listing', 'listing_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class WishlistSerializer(serializers.ModelSerializer):
    """Serializer for user's wishlist."""
    items = WishlistItemSerializer(many=True, read_only=True)
    total_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Wishlist
        fields = ['id', 'user', 'items', 'total_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class SellerWithdrawalRequestSerializer(serializers.ModelSerializer):
    """Read-only snapshot of a payout request (created via OrderViewSet.request_withdrawal)."""

    payout_method_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = SellerWithdrawalRequest
        fields = [
            'id',
            'amount',
            'currency',
            'payout_method_id',
            'status',
            'seller_note',
            'admin_note',
            'created_at',
            'updated_at',
        ]
        read_only_fields = (
            'id',
            'amount',
            'currency',
            'payout_method_id',
            'status',
            'seller_note',
            'admin_note',
            'created_at',
            'updated_at',
        )


class ListingOfferSerializer(serializers.ModelSerializer):
    listing_title = serializers.CharField(source='listing.title', read_only=True)

    class Meta:
        model = ListingOffer
        fields = [
            'id',
            'listing',
            'listing_title',
            'buyer',
            'seller',
            'status',
            'listed_price',
            'current_amount',
            'buyer_note',
            'seller_note',
            'last_actor',
            'counter_round',
            'accepted_until',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'listing',
            'listing_title',
            'buyer',
            'seller',
            'status',
            'listed_price',
            'current_amount',
            'buyer_note',
            'seller_note',
            'last_actor',
            'counter_round',
            'accepted_until',
            'created_at',
            'updated_at',
        ]
