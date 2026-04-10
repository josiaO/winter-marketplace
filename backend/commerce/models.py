"""
Commerce Models: Cart, Order, Delivery, StockReservation

Financial models (escrow, payout, dispute) are in escrow_engine.
"""
from django.db import models
from django.conf import settings
from .constants import (
    OrderStatus,
    StockReservationStatus,
    DeliveryStatus
)
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.utils import timezone
from core.models.base import BaseModel
# Replacing CloudinaryField with standard FileField for robust environmental fallback
# from cloudinary.models import CloudinaryField


class Cart(BaseModel):
    """Shopping cart for marketplace products."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart'
    )

    class Meta:
        verbose_name = _("Cart")
        verbose_name_plural = _("Carts")

    def __str__(self):
        return f"Cart for {self.user.username}"

    @property
    def total(self):
        """Calculate total cart value."""
        return sum(item.subtotal for item in self.items.all())

class CommissionRule(BaseModel):
    """
    Dynamic platform commission rules engine.
    """
    name = models.CharField(max_length=100)
    
    RULE_TYPES = (
        ('percentage', 'Percentage Only'),
        ('fixed', 'Fixed Flat Fee'),
        ('hybrid', 'Percentage + Fixed'),
    )
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES, default='percentage')
    
    percentage_value = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=5.00,
        help_text="e.g., 5.00 for 5%"
    )
    fixed_value = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="e.g., flat 1,000 TZS fee"
    )
    
    # Targeting parameters
    category = models.ForeignKey(
        'catalog.Category', 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        help_text="If blank, applies to all categories"
    )
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=0,
        help_text="Higher priority rules override lower ones if multiple match."
    )

    class Meta:
        ordering = ['-priority']

    def __str__(self):
        return f"{self.name} - {self.rule_type}"


class CartItem(BaseModel):
    """Item in shopping cart."""
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    listing = models.ForeignKey(
        'listings.Listing',
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    price_at_time = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Price snapshot when added to cart"
    )

    class Meta:
        verbose_name = _("Cart Item")
        verbose_name_plural = _("Cart Items")
        unique_together = ('cart', 'listing')

    def __str__(self):
        if self.listing:
            return f"{self.quantity}x {self.listing.title}"
        return f"{self.quantity}x [Deleted Listing]"

    @property
    def subtotal(self):
        """Calculate line item total."""
        if self.price_at_time is None or self.quantity is None:
            return None
        return self.price_at_time * self.quantity


class Wishlist(BaseModel):
    """User's wishlist/saved items."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist'
    )

    class Meta:
        verbose_name = _("Wishlist")
        verbose_name_plural = _("Wishlists")

    def __str__(self):
        return f"Wishlist for {self.user.username}"

    @property
    def total_count(self):
        """Count of items in wishlist."""
        return self.items.count()


class WishlistItem(BaseModel):
    """Item in user's wishlist."""
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name='items'
    )
    listing = models.ForeignKey(
        'listings.Listing',
        on_delete=models.CASCADE,
        related_name='wishlist_items'
    )

    class Meta:
        verbose_name = _("Wishlist Item")
        verbose_name_plural = _("Wishlist Items")
        unique_together = ('wishlist', 'listing')
        ordering = ['-created_at']

    def __str__(self):
        if self.listing:
            return f"{self.listing.title} in wishlist"
        return "[Deleted Listing] in wishlist"


class OrderQuerySet(models.QuerySet):
    """Prevents silent bulk status corruption (Python-level guard; not a DB trigger)."""

    def update(self, **kwargs):
        if 'status' in kwargs:
            raise RuntimeError(
                'Bulk Order.status update is forbidden. Use OrderLifecycleManager.'
            )
        return super().update(**kwargs)


class OrderManager(models.Manager.from_queryset(OrderQuerySet)):
    pass


class Order(BaseModel):
    """Order created from cart checkout."""
    objects = OrderManager()

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders_as_buyer'
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders_as_seller'
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True
    )
    
    # Financial Breakdown
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Sum of all order items"
    )
    shipping_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Shipping/delivery cost"
    )
    platform_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Platform commission/fee"
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total amount (subtotal + shipping + platform_fee)"
    )
    currency = models.CharField(max_length=3, default='TZS')
    
    # Shipping/Delivery
    shipping_address = models.TextField(blank=True)
    shipping_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="standard, express, pickup, etc."
    )
    tracking_number = models.CharField(max_length=100, blank=True)
    
    arrival_location = models.CharField(
        max_length=255, 
        blank=True, 
        help_text="Exact location where the order arrived (provided by seller)"
    )
    
    # Order Notes
    buyer_notes = models.TextField(
        blank=True,
        help_text="Notes from buyer"
    )
    seller_notes = models.TextField(
        blank=True,
        help_text="Internal notes from seller"
    )
    admin_notes = models.TextField(
        blank=True,
        help_text="Internal notes from platform administrators"
    )

    # Shipment Evidence
    shipment_video = models.FileField(upload_to='shipments/videos/', null=True, blank=True)
    shipment_images_count = models.PositiveIntegerField(default=0, help_text="Number of evidence images uploaded")
    
    # Timestamps
    confirmed_at = models.DateTimeField(null=True, blank=True)
    processing_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True, help_text="When the package arrived at its destination")
    delivered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer', 'status', '-created_at']),
            models.Index(fields=['seller', 'status', '-created_at']),
        ]

    def __str__(self):
        return f"Order #{self.id} - {self.buyer.username} → {self.seller.username}"
        
    def clean(self):
        super().clean()
        if self.pk:
            old_instance = Order.objects.get(pk=self.pk)
            # Enforce state machine rules
            valid_transitions = {
                'pending': ['confirmed', 'processing', 'shipped', 'arrived', 'delivered', 'completed', 'cancelled'],
                'confirmed': ['processing', 'shipped', 'arrived', 'delivered', 'completed', 'cancelled'],
                'processing': ['shipped', 'arrived', 'delivered', 'completed', 'cancelled'],
                'shipped': ['arrived', 'delivered', 'completed', 'disputed', 'cancelled'],
                'arrived': ['delivered', 'completed', 'disputed', 'cancelled'],
                'delivered': ['completed', 'disputed', 'cancelled'],
                'completed': [],
                'cancelled': [],
                'disputed': ['completed', 'cancelled', 'refunded']
            }
            if old_instance.status != self.status and self.status not in valid_transitions.get(old_instance.status, []):
                from django.core.exceptions import ValidationError
                raise ValidationError(f"Invalid transition from {old_instance.status} to {self.status}")

    def save(self, *args, **kwargs):
        from commerce.services.order_mutations import order_status_mutation_is_allowed

        bypass = kwargs.pop('_allow_status_mutation', False)
        update_fields = kwargs.get('update_fields')

        allowed = (
            bypass
            or getattr(self, '_allow_status_transition', False)
            or order_status_mutation_is_allowed()
        )
        if self.pk and not allowed:
            if update_fields is None or 'status' in update_fields:
                prev_status = (
                    type(self).objects.filter(pk=self.pk).values_list('status', flat=True).first()
                )
                if prev_status is not None and prev_status != self.status:
                    from django.core.exceptions import ValidationError

                    raise ValidationError(
                        'Direct order status mutation is forbidden. Use OrderLifecycleManager '
                        'or escrow-driven order_escrow_sync helpers.'
                    )

        self.clean()
        super().save(*args, **kwargs)
    
    def calculate_subtotal(self):
        """Calculate subtotal from order items."""
        if not self.pk:
            # Order not saved yet, can't access items
            self.subtotal = 0
            return 0
        
        from django.db.models import Sum, F
        subtotal = self.items.aggregate(
            total=Sum(F('price_at_time') * F('quantity'))
        )['total']
        self.subtotal = subtotal if subtotal is not None else 0
        return self.subtotal
    
    def calculate_total(self):
        """Calculate total amount including fees."""
        # Recalculate subtotal from items if not already set
        if self.pk:
            self.calculate_subtotal()
        self.total_amount = self.subtotal + self.shipping_cost + self.platform_fee
        return self.total_amount
    
    @property
    def seller_payout_amount(self):
        """Amount seller receives after platform fee."""
        if self.subtotal is None or self.platform_fee is None:
            return None
        return self.subtotal - self.platform_fee



class OrderEvidence(BaseModel):
    """Evidence for order shipment or delivery quality."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='evidence')
    file = models.FileField(upload_to='order_evidence/')
    media_type = models.CharField(
        max_length=10,
        choices=(('image', 'Image'), ('video', 'Video')),
        default='image'
    )
    caption = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _("Order Evidence")
        verbose_name_plural = _("Order Evidence Items")


class OrderItem(BaseModel):
    """Item in an order."""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    listing = models.ForeignKey(
        'listings.Listing',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Unlinked if listing is deleted or owner is banned"
    )
    quantity = models.PositiveIntegerField()
    price_at_time = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    class Meta:
        verbose_name = _("Order Item")
        verbose_name_plural = _("Order Items")

    def __str__(self):
        if self.listing:
            return f"{self.quantity}x {self.listing.title}"
        return f"{self.quantity}x [Deleted Listing]"

    @property
    def subtotal(self):
        """Calculate line item total."""
        if self.price_at_time is None or self.quantity is None:
            return None
        return self.price_at_time * self.quantity



class StockReservation(BaseModel):
    """
    Stock reservation during checkout process.
    Prevents overselling by reserving inventory between cart and order completion.
    """
    listing = models.ForeignKey(
        'listings.Listing',
        on_delete=models.CASCADE,
        related_name='stock_reservations'
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='stock_reservations',
        null=True,
        blank=True,
        help_text="Order this reservation is for (null if cart reservation)"
    )
    cart_item = models.ForeignKey(
        CartItem,
        on_delete=models.CASCADE,
        related_name='stock_reservation',
        null=True,
        blank=True,
        help_text="Cart item this reservation is for"
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    
    # Reservation Status
    status = models.CharField(
        max_length=20,
        choices=StockReservationStatus.choices,
        default=StockReservationStatus.RESERVED,
        db_index=True
    )
    
    # Expiration
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="When reservation expires (typically 15-30 minutes)"
    )
    
    class Meta:
        verbose_name = _("Stock Reservation")
        verbose_name_plural = _("Stock Reservations")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['listing', 'status', 'expires_at']),
            models.Index(fields=['status', 'expires_at']),
        ]
    
    def __str__(self):
        if self.listing:
            return f"Reservation: {self.quantity}x {self.listing.title} ({self.status})"
        return f"Reservation: {self.quantity}x [Deleted Listing] ({self.status})"
    
    def is_expired(self):
        """Check if reservation has expired."""
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at
    
    def release(self):
        """Release reserved stock back to inventory."""
        if self.status == 'released':
            return
        self.listing.release_stock(self.quantity)
        self.status = 'released'
        self.save(update_fields=['status'])


class Delivery(BaseModel):
    """
    Delivery/Shipping tracking for orders.
    Supports multiple delivery methods (shipping, pickup, digital).
    """
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='delivery'
    )
    
    # Delivery Method
    DELIVERY_METHODS = (
        ('shipping', _('Shipping')),
        ('pickup', _('Pickup')),
        ('digital', _('Digital Delivery')),
        ('local_delivery', _('Local Delivery')),
    )
    method = models.CharField(
        max_length=20,
        choices=DELIVERY_METHODS,
        default='shipping',
        db_index=True
    )
    
    # Shipping Address
    recipient_name = models.CharField(max_length=200, blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    address_line1 = models.CharField(max_length=300)
    address_line2 = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='Tanzania')
    
    # Tracking
    tracking_number = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Carrier tracking number"
    )
    carrier = models.CharField(
        max_length=50,
        blank=True,
        help_text="Shipping carrier (DHL, FedEx, etc.)"
    )
    tracking_url = models.URLField(blank=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True
    )
    
    # Timestamps
    shipped_at = models.DateTimeField(null=True, blank=True)
    estimated_delivery = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery Notes
    delivery_notes = models.TextField(blank=True)
    signature_required = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = _("Delivery")
        verbose_name_plural = _("Deliveries")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['tracking_number']),
        ]
    
    def __str__(self):
        return f"Delivery for Order #{self.order.id} - {self.status}"


class OrderAuditLog(BaseModel):
    """
    Append-only audit trail for security-sensitive order actions.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=64, db_index=True)
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='commerce_order_audit_entries',
    )
    metadata = models.JSONField(default=dict, blank=True)
    correlation_id = models.CharField(
        max_length=64,
        blank=True,
        help_text=_('HTTP / worker correlation id for tracing checkout → payment → escrow.'),
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Order audit log')
        verbose_name_plural = _('Order audit logs')
        indexes = [
            models.Index(fields=['order', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['correlation_id', '-created_at']),
        ]

    def __str__(self):
        return f'{self.action} order={self.order_id}'

