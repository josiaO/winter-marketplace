"""
commerce.services.cart_service
-------------------------------
Specialized service for managing the shopping cart, items, 
and stock availability checks.
"""
import logging
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from commerce.models import Cart, CartItem, StockReservation
from listings.models import Listing

logger = logging.getLogger(__name__)

def get_or_create_cart(user) -> Cart:
    """Retrieve or create a cart for the user and clean up ghost items."""
    cart, _ = Cart.objects.get_or_create(user=user)
    remove_ghost_items(cart)
    return cart

def remove_ghost_items(cart: Cart) -> int:
    """Removes items from listings whose sellers are no longer active."""
    ghost_items = []
    for item in cart.items.all():
        item.listing.refresh_from_db()
        if item.listing.is_ghost_listing:
            ghost_items.append(item)
    
    count = len(ghost_items)
    if count > 0:
        for item in ghost_items:
            item.delete()
        logger.info("Removed %d ghost items from cart %s", count, cart.id)
    return count

def add_to_cart(cart: Cart, listing_id: int, quantity: int = 1) -> CartItem:
    """Adds a listing to the cart with stock validation (serialized per listing row)."""
    with transaction.atomic():
        listing = get_object_or_404(
            Listing.objects.select_related('owner', 'owner__seller_profile', 'store').select_for_update(
                of=('self',)
            ),
            id=listing_id,
        )

        if listing.is_ghost_listing:
            raise ValueError("This seller is no longer active. You cannot purchase this item.")

        validate_stock_availability(listing, quantity, cart=cart)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            listing=listing,
            defaults={'price_at_time': listing.price, 'quantity': quantity},
        )

        if not created:
            new_quantity = cart_item.quantity + quantity
            validate_stock_availability(listing, new_quantity, cart=cart, is_update=True)
            cart_item.quantity = new_quantity
            cart_item.price_at_time = listing.price
            cart_item.save()

        return cart_item

def validate_stock_availability(listing: Listing, required_quantity: int, cart=None, is_update=False):
    """
    Checks if the required quantity is available, accounting for 
    other active stock reservations.
    """
    if not listing.track_inventory:
        return True

    # Get all active reservations for this listing
    active_reservations = StockReservation.objects.filter(
        listing=listing,
        status__in=['reserved', 'confirmed'],
        expires_at__gt=timezone.now()
    )
    reserved_amount = sum(r.quantity for r in active_reservations)

    # Quantities already sitting in other users' carts reduce what this cart may take
    # (cart lines are not DB reservations, but we serialize adds per listing with
    # select_for_update so this sum stays consistent with checkout validation).
    other_cart_qty = 0
    if cart is not None:
        agg = (
            CartItem.objects.filter(listing=listing)
            .exclude(cart=cart)
            .aggregate(total=Sum('quantity'))
        )
        other_cart_qty = int(agg['total'] or 0)

    effective_available = listing.stock_quantity - reserved_amount - other_cart_qty

    # NOTE: Cart items in this cart are validated via required_quantity above;
    # checkout still performs authoritative stock / reservation checks.
    
    if effective_available < required_quantity:
        if not listing.allow_backorders:
            raise ValueError(f"Insufficient stock. Only {max(0, effective_available)} available.")
    
    return True
