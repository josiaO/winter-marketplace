"""
Stock reservation coordination (commerce domain).

Source of truth for on-hand quantity is listings.Listing; reservations live in commerce.StockReservation.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from commerce.models import StockReservation
from listings.models import Listing


class InventoryService:
    """Reserve and release stock for cart/checkout flows."""

    @staticmethod
    @transaction.atomic
    def reserve_stock(listing, quantity, order=None, cart_item=None, expires_minutes=30):
        if not listing.track_inventory:
            return None

        listing = Listing.objects.select_for_update().get(pk=listing.pk)

        InventoryService.cleanup_expired_reservations()

        existing_reservations = StockReservation.objects.filter(
            listing=listing,
            status__in=['reserved', 'confirmed'],
            expires_at__gt=timezone.now(),
        )

        if cart_item:
            cart_item_reservation = existing_reservations.filter(cart_item=cart_item).first()
            if cart_item_reservation:
                reserved_quantity = sum(
                    r.quantity for r in existing_reservations.exclude(id=cart_item_reservation.id)
                )
            else:
                reserved_quantity = sum(r.quantity for r in existing_reservations)
        else:
            reserved_quantity = sum(r.quantity for r in existing_reservations)

        available = listing.stock_quantity - reserved_quantity

        if available < quantity:
            if not listing.allow_backorders:
                return None

        if cart_item:
            existing_reservation = StockReservation.objects.filter(
                listing=listing,
                cart_item=cart_item,
                status__in=['reserved', 'confirmed'],
                expires_at__gt=timezone.now(),
            ).first()

            if existing_reservation:
                old_quantity = existing_reservation.quantity
                existing_reservation.quantity = quantity
                existing_reservation.expires_at = timezone.now() + timedelta(minutes=expires_minutes)
                if order:
                    existing_reservation.order = order
                existing_reservation.save()

                listing.release_stock(old_quantity)
                listing.reserve_stock(quantity)

                return existing_reservation

        reservation = StockReservation.objects.create(
            listing=listing,
            order=order,
            cart_item=cart_item,
            quantity=quantity,
            expires_at=timezone.now() + timedelta(minutes=expires_minutes),
        )

        listing.reserve_stock(quantity)

        return reservation

    @staticmethod
    def confirm_reservation(reservation):
        reservation.status = 'confirmed'
        reservation.save(update_fields=['status'])
        return reservation

    @staticmethod
    def release_reservation(reservation):
        reservation.release()
        return reservation

    @staticmethod
    def cleanup_expired_reservations():
        expired = StockReservation.objects.filter(
            status__in=['reserved', 'confirmed'],
            expires_at__lte=timezone.now(),
        )
        for reservation in expired:
            reservation.release()
        return expired.count()
