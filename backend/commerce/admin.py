"""
Commerce Admin: Order, Cart, Escrow, Payout, Delivery, StockReservation, CommissionRule
"""
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import (
    Cart, CartItem, Order, OrderItem,
    Delivery, StockReservation, CommissionRule, OrderAuditLog
)
from commerce.services.inventory import InventoryService
from commerce.services.lifecycle import OrderLifecycleManager


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('get_subtotal',)
    
    def get_subtotal(self, obj):
        """Display subtotal in admin."""
        if obj and obj.price_at_time is not None and obj.quantity is not None:
            return obj.subtotal
        return '-'
    get_subtotal.short_description = 'Subtotal'


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'item_count', 'total', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('total', 'created_at', 'updated_at')
    inlines = [CartItemInline]
    
    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Items'
    
    def save_formset(self, request, form, formset, change):
        """Override to auto-populate price_at_time from listing price."""
        instances = formset.save(commit=False)
        for instance in instances:
            # Auto-populate price_at_time from listing if not set
            if instance.listing and (not instance.price_at_time or instance.price_at_time == 0):
                instance.price_at_time = instance.listing.price
            instance.save()
        
        # Handle deletions
        for obj in formset.deleted_objects:
            obj.delete()
        
        formset.save_m2m()


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'listing', 'quantity', 'price_at_time', 'get_subtotal')
    search_fields = ('listing__title', 'cart__user__username')
    list_filter = ('created_at',)
    
    def get_subtotal(self, obj):
        """Display subtotal in admin."""
        if obj.price_at_time is not None and obj.quantity is not None:
            return obj.subtotal
        return '-'
    get_subtotal.short_description = 'Subtotal'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('price_at_time', 'get_subtotal')
    
    def get_subtotal(self, obj):
        """Display subtotal in admin."""
        if obj and obj.price_at_time is not None and obj.quantity is not None:
            return obj.subtotal
        return '-'
    get_subtotal.short_description = 'Subtotal'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'buyer', 'seller', 'status', 'total_amount', 'currency',
        'created_at', 'completed_at'
    )
    list_filter = ('status', 'currency', 'created_at')
    search_fields = (
        'buyer__username', 'seller__username', 'tracking_number',
        'id'
    )
    readonly_fields = (
        'status',
        'subtotal', 'platform_fee', 'total_amount', 'get_seller_payout_amount',
        'confirmed_at', 'processing_at', 'shipped_at',
        'delivered_at', 'completed_at', 'cancelled_at',
        'created_at', 'updated_at',
    )
    
    def get_seller_payout_amount(self, obj):
        """Display seller payout amount in admin."""
        if obj.pk and obj.subtotal is not None and obj.platform_fee is not None:
            return obj.seller_payout_amount
        return '-'
    get_seller_payout_amount.short_description = 'Seller Payout Amount'
    
    def save_model(self, request, obj, form, change):
        """Override save to ensure defaults are set."""
        # Set defaults if not provided (for new orders)
        if not change:  # Creating new order
            if obj.subtotal is None:
                obj.subtotal = 0
            if obj.total_amount is None:
                obj.total_amount = 0
        
        # Save the order (needed for inlines)
        super().save_model(request, obj, form, change)
    
    def save_related(self, request, form, formsets, change):
        """Override to recalculate totals after items are saved."""
        super().save_related(request, form, formsets, change)
        
        # Recalculate after items are saved
        obj = form.instance
        if obj.pk:
            obj.calculate_subtotal()
            obj.calculate_total()
            obj.save(update_fields=['subtotal', 'total_amount'])

    def save_formset(self, request, form, formset, change):
        """Override to auto-populate price_at_time from listing price."""
        instances = formset.save(commit=False)
        for instance in instances:
            # Auto-populate price_at_time from listing if not set
            if hasattr(instance, 'listing') and instance.listing and (not instance.price_at_time or instance.price_at_time == 0):
                instance.price_at_time = instance.listing.price
            instance.save()
        
        # Handle deletions
        for obj in formset.deleted_objects:
            obj.delete()
        
        formset.save_m2m()
    
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('buyer', 'seller', 'status', 'currency')
        }),
        ('Financials', {
            'fields': (
                'subtotal', 'shipping_cost', 'platform_fee',
                'total_amount', 'get_seller_payout_amount'
            )
        }),
        ('Shipping', {
            'fields': (
                'shipping_address', 'shipping_method', 'tracking_number'
            )
        }),
        ('Notes', {
            'fields': ('buyer_notes', 'seller_notes')
        }),
        ('Timestamps', {
            'fields': (
                'confirmed_at', 'processing_at', 'shipped_at',
                'delivered_at', 'completed_at', 'cancelled_at',
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_confirmed', 'mark_shipped', 'mark_completed', 'cancel_order']
    
    def mark_confirmed(self, request, queryset):
        n = 0
        for order in queryset.filter(status='pending'):
            try:
                OrderLifecycleManager.confirm_order(order, actor=request.user)
                n += 1
            except ValueError as e:
                self.message_user(request, f"Order {order.pk}: {e}", level='WARNING')
        self.message_user(request, f"Marked {n} order(s) as confirmed (lifecycle + escrow sync).")
    mark_confirmed.short_description = "Mark as confirmed"
    
    def mark_shipped(self, request, queryset):
        n = 0
        for order in queryset.filter(status__in=['confirmed', 'processing']):
            try:
                OrderLifecycleManager.ship_order(order, actor=request.user)
                n += 1
            except ValueError as e:
                self.message_user(request, f"Order {order.pk}: {e}", level='WARNING')
        self.message_user(request, f"Marked {n} order(s) as shipped (lifecycle + escrow sync).")
    mark_shipped.short_description = "Mark as shipped"
    
    def mark_completed(self, request, queryset):
        n = 0
        for order in queryset.filter(status__in=['shipped', 'arrived', 'delivered']):
            try:
                OrderLifecycleManager.confirm_receipt(order, actor=request.user)
                n += 1
            except ValueError as e:
                self.message_user(request, f"Order {order.pk}: {e}", level='WARNING')
        self.message_user(request, f"Completed {n} order(s) via confirm_receipt (releases escrow when applicable).")
    mark_completed.short_description = "Mark as completed"
    
    def cancel_order(self, request, queryset):
        n = 0
        for order in queryset.filter(
            status__in=['pending', 'confirmed', 'processing']
        ):
            try:
                OrderLifecycleManager.cancel_order(
                    order,
                    actor=request.user,
                    reason='Admin bulk cancel',
                )
                n += 1
            except ValueError as e:
                self.message_user(request, f"Order {order.pk}: {e}", level='WARNING')
        self.message_user(request, f"Cancelled {n} order(s) (lifecycle + escrow refund when applicable).")
    cancel_order.short_description = "Cancel orders"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'listing', 'quantity', 'price_at_time', 'get_subtotal')
    search_fields = ('listing__title', 'order__id')
    list_filter = ('created_at',)
    
    def get_subtotal(self, obj):
        """Display subtotal in admin."""
        if obj.price_at_time is not None and obj.quantity is not None:
            return obj.subtotal
        return '-'
    get_subtotal.short_description = 'Subtotal'




@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = (
        'order', 'method', 'status', 'tracking_number',
        'carrier', 'shipped_at', 'delivered_at'
    )
    list_filter = ('method', 'status', 'created_at')
    search_fields = (
        'order__id', 'tracking_number', 'recipient_name',
        'recipient_phone'
    )
    readonly_fields = (
        'shipped_at', 'delivered_at',
        'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Order & Method', {
            'fields': ('order', 'method', 'status')
        }),
        ('Recipient', {
            'fields': (
                'recipient_name', 'recipient_phone'
            )
        }),
        ('Address', {
            'fields': (
                'address_line1', 'address_line2', 'city',
                'region', 'postal_code', 'country'
            )
        }),
        ('Tracking', {
            'fields': (
                'tracking_number', 'carrier', 'tracking_url'
            )
        }),
        ('Delivery Details', {
            'fields': (
                'delivery_notes', 'signature_required',
                'estimated_delivery'
            )
        }),
        ('Timestamps', {
            'fields': (
                'shipped_at', 'delivered_at',
                'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_shipped', 'mark_delivered']
    
    def mark_shipped(self, request, queryset):
        queryset.filter(status='preparing').update(
            status='in_transit',
            shipped_at=timezone.now()
        )
        self.message_user(request, "Selected deliveries marked as shipped.")
    mark_shipped.short_description = "Mark as shipped"
    
    def mark_delivered(self, request, queryset):
        queryset.filter(status='out_for_delivery').update(
            status='delivered',
            delivered_at=timezone.now()
        )
        self.message_user(request, "Selected deliveries marked as delivered.")
    mark_delivered.short_description = "Mark as delivered"


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'listing', 'order', 'quantity', 'status',
        'expires_at', 'is_expired_display'
    )
    list_filter = ('status', 'created_at', 'expires_at')
    search_fields = ('listing__title', 'order__id')
    readonly_fields = ('is_expired_display', 'created_at', 'updated_at')
    
    def is_expired_display(self, obj):
        return obj.is_expired()
    is_expired_display.boolean = True
    is_expired_display.short_description = 'Expired'
    
    actions = ['release_reservations', 'cleanup_expired']
    
    def release_reservations(self, request, queryset):
        count = 0
        for reservation in queryset.filter(status__in=['reserved', 'confirmed']):
            reservation.release()
            count += 1
        self.message_user(request, f"{count} reservations released.")
    release_reservations.short_description = "Release selected reservations"
    
    def cleanup_expired(self, request, queryset):
        count = InventoryService.cleanup_expired_reservations()
        self.message_user(request, f"{count} expired reservations cleaned up.")
    cleanup_expired.short_description = "Cleanup expired reservations"


@admin.register(OrderAuditLog)
class OrderAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order',
        'action',
        'from_status',
        'to_status',
        'actor',
        'correlation_id',
        'created_at',
    )
    list_filter = ('action', 'created_at')
    search_fields = ('order__id', 'action', 'correlation_id')
    readonly_fields = (
        'order',
        'action',
        'from_status',
        'to_status',
        'actor',
        'metadata',
        'correlation_id',
        'created_at',
        'updated_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CommissionRule)
class CommissionRuleAdmin(admin.ModelAdmin):
    """Admin interface for managing platform commission rules."""
    list_display = (
        'name', 'rule_type', 'get_commission_display', 'category', 
        'priority', 'is_active', 'created_at'
    )
    list_filter = ('rule_type', 'is_active', 'category', 'created_at')
    search_fields = ('name', 'category__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Rule Information', {
            'fields': ('name', 'rule_type', 'is_active', 'priority')
        }),
        ('Commission Settings', {
            'fields': ('percentage_value', 'fixed_value'),
            'description': 'For percentage: enter value like 5.00 for 5%. For fixed: enter flat fee amount. For hybrid: both apply.'
        }),
        ('Targeting', {
            'fields': ('category',),
            'description': 'Leave category blank to apply to all categories. Higher priority rules override lower ones.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_commission_display(self, obj):
        """Display commission in a readable format."""
        if obj.rule_type == 'percentage':
            return f"{obj.percentage_value}%"
        elif obj.rule_type == 'fixed':
            return f"Fixed: {obj.fixed_value}"
        elif obj.rule_type == 'hybrid':
            return f"{obj.percentage_value}% + {obj.fixed_value}"
        return '-'
    get_commission_display.short_description = 'Commission'
    
    actions = ['activate_rules', 'deactivate_rules']
    
    def activate_rules(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} commission rules activated.")
    activate_rules.short_description = "Activate selected rules"
    
    def deactivate_rules(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} commission rules deactivated.")
    deactivate_rules.short_description = "Deactivate selected rules"
