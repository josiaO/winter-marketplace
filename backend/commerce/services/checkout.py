"""
Order creation and checkout orchestration (commerce domain).

Escrow transaction creation runs here — not in marketplace.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone as dj_tz

from commerce.models import Order, OrderItem, StockReservation, ListingOffer
from commerce.services.inventory import InventoryService
from commerce.services.lifecycle import OrderLifecycleManager
from commerce.services.shipping_rates import shipping_cost_for_method
from listings.models import Listing


class OrderService:
    """Create orders from cart, reserve stock, and link escrow transactions."""

    @staticmethod
    def calculate_platform_fee(listing, amount, *, seller=None):
        from django.db.models import Q

        from commerce.models import CommissionRule

        subtotal = Decimal(str(amount))
        category_id = getattr(listing, 'category_id', None) if listing is not None else None
        qs = CommissionRule.objects.filter(is_active=True)
        if category_id:
            qs = qs.filter(Q(category_id=category_id) | Q(category__isnull=True))
        else:
            qs = qs.filter(category__isnull=True)
        rules = list(qs.order_by('-priority', '-id'))
        rule = None
        if rules:
            top_p = rules[0].priority
            tier = [r for r in rules if r.priority == top_p]
            if category_id:
                rule = next((r for r in tier if r.category_id == category_id), tier[0])
            else:
                rule = tier[0]

        if rule is None:
            from core.models import SiteConfiguration

            config = SiteConfiguration.get_solo()
            # `platform_fee` may be stored as float in SiteConfiguration; normalize to Decimal.
            platform_fee = config.platform_fee
            fee_dec = platform_fee if isinstance(platform_fee, Decimal) else Decimal(str(platform_fee or 0))
            default_comm = fee_dec / Decimal('100.0')
            return subtotal * default_comm

        fee = Decimal('0')
        if rule.rule_type == 'percentage':
            percentage = rule.percentage_value
            if not isinstance(percentage, Decimal):
                percentage = Decimal(str(percentage))
            fee = subtotal * (percentage / Decimal('100.0'))
        elif rule.rule_type == 'fixed':
            fee = rule.fixed_value
            if not isinstance(fee, Decimal):
                fee = Decimal(str(fee))
        elif rule.rule_type == 'hybrid':
            fixed = rule.fixed_value
            if not isinstance(fixed, Decimal):
                fixed = Decimal(str(fixed))
            percentage = rule.percentage_value
            if not isinstance(percentage, Decimal):
                percentage = Decimal(str(percentage))
            fee = fixed + (subtotal * (percentage / Decimal('100.0')))

        return fee

    @staticmethod
    def _listing_delivery_total_for_cart_items(cart_items) -> Decimal:
        """
        Sum (delivery_fee * quantity) for lines where the listing charges delivery.
        When this is > 0, it becomes the order shipping_cost (seller-defined).
        Otherwise checkout falls back to platform COMMERCE_SHIPPING_RATES for the method.
        """
        total = Decimal('0')
        for cart_item in cart_items:
            listing = cart_item.listing
            if getattr(listing, 'delivery_is_free', True):
                continue
            fee = getattr(listing, 'delivery_fee', None)
            if fee is None:
                continue
            fee_dec = fee if isinstance(fee, Decimal) else Decimal(str(fee))
            if fee_dec <= 0:
                continue
            qty = getattr(cart_item, 'quantity', 1) or 1
            total += fee_dec * Decimal(qty)
        return total

    @staticmethod
    @transaction.atomic
    def create_order_from_cart(
        cart,
        shipping_address,
        shipping_method='standard',
        payment_method='mpesa',
        *,
        listing_offer=None,
    ):
        if not cart.items.exists():
            raise ValueError('Cart is empty')

        if listing_offer is not None:
            if listing_offer.buyer_id != cart.user.id:
                raise ValueError('This offer does not belong to you.')
            if listing_offer.status != ListingOffer.Status.ACCEPTED:
                raise ValueError('This offer is not in an accepted state.')
            if not listing_offer.accepted_until or listing_offer.accepted_until < dj_tz.now():
                raise ValueError('This accepted offer has expired. Ask the seller for a new price.')
            cart_listing_ids = {int(x.listing_id) for x in cart.items.all()}
            if int(listing_offer.listing_id) not in cart_listing_ids:
                raise ValueError('Add the negotiated listing to your cart before checkout.')

        items_by_seller = {}
        for item in cart.items.select_related('listing', 'listing__owner'):
            listing = Listing.objects.select_for_update().get(pk=item.listing_id)

            if listing.is_ghost_listing:
                raise ValueError(
                    f"Cannot checkout: Listing '{listing.title}' is no longer available as the seller is inactive."
                )

            seller = listing.owner
            if seller not in items_by_seller:
                items_by_seller[seller] = []
            item.listing = listing
            items_by_seller[seller].append(item)

        orders = []

        for seller, items in items_by_seller.items():
            if seller.id == cart.user.id:
                raise ValueError(
                    f'Cannot create order: Seller and buyer cannot be the same user (User ID: {seller.id})'
                )

            subtotal = sum(item.subtotal for item in items)
            thread_offer = (
                listing_offer
                if listing_offer is not None and int(listing_offer.seller_id) == int(seller.id)
                else None
            )
            if thread_offer is not None:
                adj = Decimal('0')
                for item in items:
                    if int(item.listing_id) == int(thread_offer.listing_id):
                        line = thread_offer.current_amount * Decimal(item.quantity)
                        orig = item.subtotal
                        adj += orig - line
                subtotal = subtotal - adj
                if subtotal < Decimal('0'):
                    subtotal = Decimal('0')
            primary_listing = items[0].listing
            platform_fee = OrderService.calculate_platform_fee(
                primary_listing,
                subtotal,
                seller=seller,
            )
            listing_delivery = OrderService._listing_delivery_total_for_cart_items(items)
            if listing_delivery > 0:
                shipping_cost = listing_delivery
            else:
                try:
                    shipping_cost = shipping_cost_for_method(shipping_method)
                except ValueError:
                    shipping_cost = Decimal('0')
            total = subtotal + shipping_cost + platform_fee

            order = Order.objects.create(
                buyer=cart.user,
                seller=seller,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                platform_fee=platform_fee,
                total_amount=total,
                shipping_address=shipping_address,
                shipping_method=shipping_method,
                status='pending',
            )

            from commerce.models import Delivery

            Delivery.objects.create(
                order=order,
                method=shipping_method if shipping_method in dict(Delivery.DELIVERY_METHODS) else 'shipping',
                address_line1=shipping_address[:300],
                recipient_name=cart.user.get_full_name() or cart.user.username,
                recipient_phone=getattr(cart.user, 'phone', '') or '',
                city='Unknown',
                status='pending',
            )

            if order.seller.id != seller.id:
                raise ValueError(f'Order creation error: Seller mismatch. Expected {seller.id}, got {order.seller.id}')
            if order.buyer.id != cart.user.id:
                raise ValueError(
                    f'Order creation error: Buyer mismatch. Expected {cart.user.id}, got {order.buyer.id}'
                )

            InventoryService.cleanup_expired_reservations()

            for cart_item in items:
                listing = Listing.objects.select_for_update().get(pk=cart_item.listing_id)

                if listing.track_inventory:
                    existing_reservations = StockReservation.objects.filter(
                        listing=listing,
                        status__in=['reserved', 'confirmed'],
                        expires_at__gt=dj_tz.now(),
                    )
                    reserved_quantity = sum(r.quantity for r in existing_reservations)

                    cart_item_reservation = StockReservation.objects.filter(
                        listing=listing,
                        cart_item=cart_item,
                        status__in=['reserved', 'confirmed'],
                        expires_at__gt=dj_tz.now(),
                    ).first()
                    if cart_item_reservation:
                        reserved_quantity -= cart_item_reservation.quantity

                    available = listing.stock_quantity - reserved_quantity

                    if available < cart_item.quantity:
                        if not listing.allow_backorders:
                            OrderLifecycleManager.cancel_order(
                                order,
                                actor=None,
                                reason='Checkout: insufficient stock',
                            )
                            raise ValueError(
                                f'Insufficient stock for {listing.title} - {listing.id}. '
                                f'Available: {available}, Requested: {cart_item.quantity}, '
                                f'Stock: {listing.stock_quantity}, Reserved: {reserved_quantity}'
                            )

                reservation = InventoryService.reserve_stock(
                    listing=listing,
                    quantity=cart_item.quantity,
                    order=order,
                )

                if not reservation and listing.track_inventory:
                    OrderLifecycleManager.cancel_order(
                        order,
                        actor=None,
                        reason='Checkout: insufficient stock',
                    )
                    available = listing.stock_quantity - sum(
                        r.quantity
                        for r in StockReservation.objects.filter(
                            listing=listing,
                            status__in=['reserved', 'confirmed'],
                            expires_at__gt=dj_tz.now(),
                        )
                    )
                    raise ValueError(
                        f'Insufficient stock for {listing.title} - {listing.id}. '
                        f'Available: {available}, Requested: {cart_item.quantity}'
                    )

                unit_price = cart_item.price_at_time
                if thread_offer is not None and int(cart_item.listing_id) == int(thread_offer.listing_id):
                    unit_price = thread_offer.current_amount

                OrderItem.objects.create(
                    order=order,
                    listing=cart_item.listing,
                    quantity=cart_item.quantity,
                    price_at_time=unit_price,
                )

            from escrow_engine.models.transaction import TransactionSource
            from escrow_engine.services import create_transaction as _create_txn

            _create_txn(
                amount=total,
                currency=order.currency,
                source=TransactionSource.MARKETPLACE,
                buyer_user=cart.user,
                seller_user=seller,
                payment_method=payment_method,
                description=f'Marketplace order {order.id}',
                metadata={'order_id': str(order.id)},
                linked_order=order,
            )

            orders.append(order)

        if listing_offer is not None:
            listing_offer.status = ListingOffer.Status.FULFILLED
            listing_offer.save(update_fields=['status', 'updated_at'])

        cart.items.all().delete()

        from core.events import emit_event

        for order in orders:
            emit_event('ORDER_CREATED', {'order_id': order.id}, source_module='commerce.services.checkout')

        order_ids = [o.id for o in orders]

        def _enqueue_post_commit_tasks() -> None:
            from commerce.tasks import auto_cancel_unpaid_order, send_order_confirmation_email

            for oid in order_ids:
                send_order_confirmation_email.delay(oid)
                auto_cancel_unpaid_order.apply_async((oid,), countdown=86400)

        transaction.on_commit(_enqueue_post_commit_tasks)

        return orders[0] if len(orders) == 1 else orders

    @staticmethod
    def cancel_order(order):
        return OrderLifecycleManager.cancel_order(
            order,
            actor=None,
            reason='Order cancelled (OrderService.cancel_order)',
        )
