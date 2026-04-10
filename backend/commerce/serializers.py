"""
Commerce Serializers: Order, OrderItem, Cart, Delivery, StockReservation
"""
from django.conf import settings
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import (
    Cart, CartItem, Order, OrderItem, OrderEvidence,
    Delivery, StockReservation, Wishlist, WishlistItem
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
    
    class Meta:
        model = Order
        fields = [
            'id', 'orderNumber', 'buyer', 'seller', 'status',
            'subtotal', 'shipping_cost', 'platform_fee', 'total_amount', 'currency',
            'shipping_address', 'shipping_method', 'tracking_number', 'arrival_location',
            'buyer_notes', 'seller_notes',
            'seller_payout_amount', 'escrow',
            'buyer_details', 'buyer_location', 'seller_details',
            'confirmed_at', 'processing_at', 'shipped_at',
            'delivered_at', 'arrived_at', 'completed_at', 'cancelled_at',
            'items', 'listing', 'quantity', 'unitPrice',
            'totalAmount', 'platformFee', 'sellerPayout', 
            'createdAt', 'updatedAt', 'shippedAt', 'deliveredAt', 'arrivedAt',
            'buyerId', 'sellerId', 'listingId',
            'shipment_video', 'shipment_images_count', 'evidence',
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
        try:
            profile = getattr(obj.buyer, 'profile', None)
            return {
                'id': obj.buyer.id,
                'username': obj.buyer.username,
                'email': obj.buyer.email,
                'first_name': obj.buyer.first_name,
                'last_name': obj.buyer.last_name,
                'full_name': obj.buyer.get_full_name() or obj.buyer.username,
                'phone_number': profile.phone_number if profile else None,
                'address': profile.address if profile else None,
                'profile_image': profile.image.url if profile and profile.image else None,
            }
        except Exception:
            return {
                'id': obj.buyer.id,
                'username': obj.buyer.username,
                'email': obj.buyer.email,
                'first_name': obj.buyer.first_name,
                'last_name': obj.buyer.last_name,
                'full_name': obj.buyer.get_full_name() or obj.buyer.username,
            }
    
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
        try:
            profile = getattr(obj.seller, 'profile', None)
            # Check for seller profile (business info)
            seller_profile = getattr(obj.seller, 'seller_profile', None)
            return {
                'id': obj.seller.id,
                'username': obj.seller.username,
                'email': obj.seller.email,
                'first_name': obj.seller.first_name,
                'last_name': obj.seller.last_name,
                'full_name': obj.seller.get_full_name() or obj.seller.username,
                'phone_number': profile.phone_number if profile else None,
                'address': profile.address if profile else None,
                'profile_image': profile.image.url if profile and profile.image else None,
                'business_name': seller_profile.business_name if seller_profile else None,
            }
        except Exception:
            return {
                'id': obj.seller.id,
                'username': obj.seller.username,
                'email': obj.seller.email,
                'first_name': obj.seller.first_name,
                'last_name': obj.seller.last_name,
                'full_name': obj.seller.get_full_name() or obj.seller.username,
            }
    
    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_escrow(self, obj):
        """
        Return escrow state from the engine Transaction linked to this order.
        Uses order.engine_transaction (set by escrow_engine.Transaction.linked_order).
        """
        try:
            txn = obj.engine_transaction
            return {
                'id': str(txn.id),
                'reference': txn.reference,
                'amount': str(txn.amount),
                'currency': txn.currency,
                'status': txn.status,
                'payment_method': txn.payment_method,
                'gateway_reference': txn.gateway_reference,
                'payment_reference': txn.gateway_reference,
                'held_at': txn.held_at.isoformat() if txn.held_at else None,
                'released_at': txn.released_at.isoformat() if txn.released_at else None,
                'refunded_at': txn.refunded_at.isoformat() if txn.refunded_at else None,
                'dispute_reason': txn.dispute_reason or None,
                'dispute_resolved_by': (
                    txn.dispute_resolved_by.id if txn.dispute_resolved_by else None
                ),
            }
        except Exception:
            return None


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
