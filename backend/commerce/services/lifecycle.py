"""
commerce.services.lifecycle
----------------------------
Centralized service for managing the lifecycle of an Order and its
associated Escrow Engine Transaction.

Source of Truth: commerce owns Order.status and fulfilment; escrow_engine owns
Transaction status and money (hold/release/refund). This module orchestrates by
calling escrow_engine.services — it must never assign transaction.status or
confirm payment outside those services.
"""
import logging
from django.db import transaction
from django.utils import timezone
from commerce.models import Order, OrderEvidence, Delivery
from escrow_engine.models import Dispute, Transaction, TransactionStatus
import escrow_engine.services.escrow as escrow_svc
from escrow_engine.services.escrow import open_dispute as engine_open_dispute
from .registry import get_delivery_status
from .audit import write_order_audit
from .uploads import validate_commerce_upload_files
from .order_mutations import order_status_write_context
from .escrow_bridge import (
    safe_hold_funds_for_order,
    safe_refund_funds_for_order,
    safe_release_funds_for_order,
)
from .invariants import maybe_assert_order_transaction_consistency
from core.events import emit_event

logger = logging.getLogger(__name__)


def _lifecycle_paranoia(order: Order) -> None:
    maybe_assert_order_transaction_consistency(order)

class OrderLifecycleManager:
    """
    Single entry point for order state transitions (commerce domain).

    Enforced via calls to escrow_engine.services.escrow for hold/release/refund/dispute
    resolution so money state stays owned by escrow_engine only.
    """

    @staticmethod
    @transaction.atomic
    def confirm_order(order: Order, actor=None) -> Order:
        """Move order to confirmed and escrow to HOLD."""
        if order.status != 'pending':
            raise ValueError(f"Cannot confirm order in {order.status} status.")

        prev = order.status
        with order_status_write_context(order):
            now = timezone.now()
            order.status = 'confirmed'
            order.confirmed_at = now
            order.save(update_fields=['status', 'confirmed_at', 'updated_at'])

            safe_hold_funds_for_order(
                order,
                actor=actor,
                actor_label='System: Order Confirmation',
                reason='Order confirmed',
            )

            # Sync Delivery
            OrderLifecycleManager._sync_delivery(order)

            write_order_audit(
                order, 'confirm_order', actor=actor, from_status=prev, to_status=order.status
            )
        emit_event('ORDER_CONFIRMED', {'order_id': order.id}, source_module='commerce.lifecycle')
        _lifecycle_paranoia(order)
        return order

    @staticmethod
    @transaction.atomic
    def ship_order(order: Order, tracking_number: str = '', carrier: str = '', 
                   shipment_video=None, shipment_images=None, actor=None) -> Order:
        """Mark order as shipped and save evidence."""
        if order.status not in ['confirmed', 'processing']:
            raise ValueError(
                f"Cannot ship order in {order.status} status. "
                "Wait until the buyer has paid (order is confirmed) before shipping."
            )

        validate_commerce_upload_files(video=shipment_video, images=shipment_images)

        prev = order.status
        with order_status_write_context(order):
            now = timezone.now()

            order.status = 'shipped'
            order.shipped_at = now
            if tracking_number:
                order.tracking_number = tracking_number
            if carrier:
                order.shipping_method = carrier
            if shipment_video:
                order.shipment_video = shipment_video

            order.save()

            # Handle multiple shipment images
            if shipment_images:
                for img in shipment_images:
                    OrderEvidence.objects.create(
                        order=order,
                        file=img,
                        media_type='image'
                    )
                order.shipment_images_count = order.evidence.filter(media_type='image').count()
                order.save(update_fields=['shipment_images_count'])

            # Sync Delivery
            OrderLifecycleManager._sync_delivery(
                order, tracking_number=tracking_number, carrier=carrier
            )

            write_order_audit(
                order, 'ship_order', actor=actor, from_status=prev, to_status=order.status
            )
        emit_event('ORDER_SHIPPED', {'order_id': order.id}, source_module='commerce.lifecycle')
        _lifecycle_paranoia(order)
        return order

    @staticmethod
    @transaction.atomic
    def confirm_receipt(order: Order, actor=None) -> Order:
        """Buyer confirms receipt: Order to completed, Escrow to RELEASED."""
        if order.status not in ['shipped', 'arrived', 'delivered']:
            raise ValueError(f"Cannot confirm receipt for order in {order.status} status.")

        prev = order.status
        with order_status_write_context(order):
            now = timezone.now()
            order.status = 'completed'
            order.completed_at = now
            order.save(update_fields=['status', 'completed_at', 'updated_at'])

        txn = Transaction.objects.filter(linked_order=order).first()
        if txn and txn.status == TransactionStatus.HOLD:
            safe_release_funds_for_order(
                order,
                actor=actor,
                actor_label='Buyer: Confirmed Receipt',
                reason='Buyer confirmed receipt',
            )
            emit_event(
                'ESCROW_FUNDS_RELEASED',
                {'order_id': order.id, 'transaction_id': str(txn.pk)},
                source_module='commerce.lifecycle',
            )

        # Sync Delivery
        OrderLifecycleManager._sync_delivery(order)

        write_order_audit(
            order, 'confirm_receipt', actor=actor, from_status=prev, to_status=order.status
        )
        emit_event('ORDER_COMPLETED', {'order_id': order.id}, source_module='commerce.lifecycle')
        _lifecycle_paranoia(order)
        return order

    @staticmethod
    @transaction.atomic
    def cancel_order(order: Order, actor=None, reason: str = 'Order cancelled') -> Order:
        """Cancel order, release stock, and refund escrow if held."""
        if order.status in ['completed', 'cancelled', 'refunded']:
            raise ValueError(f"Cannot cancel order in {order.status} status.")
        if order.status in ['shipped', 'arrived', 'delivered', 'disputed']:
            raise ValueError(
                "Cannot cancel an order that has been shipped or is in transit. Contact support if you need help."
            )

        prev = order.status
        # 1. Release stock reservations
        for reservation in order.stock_reservations.filter(status__in=['reserved', 'confirmed']):
            reservation.release()

        with order_status_write_context(order):
            now = timezone.now()
            order.status = 'cancelled'
            order.cancelled_at = now
            order.save(update_fields=['status', 'cancelled_at', 'updated_at'])

        txn = Transaction.objects.filter(linked_order=order).first()
        if txn and txn.status in (
            TransactionStatus.PAID,
            TransactionStatus.HOLD,
            TransactionStatus.DISPUTED,
        ):
            safe_refund_funds_for_order(
                order,
                actor=actor,
                actor_label='System: Order Cancellation',
                reason=reason,
            )

        # Sync Delivery
        OrderLifecycleManager._sync_delivery(order)

        write_order_audit(
            order,
            'cancel_order',
            actor=actor,
            from_status=prev,
            to_status=order.status,
            metadata={'reason': reason},
        )
        emit_event(
            'ORDER_CANCELLED',
            {'order_id': order.id, 'reason': reason},
            source_module='commerce.lifecycle',
        )
        _lifecycle_paranoia(order)
        return order

    @staticmethod
    @transaction.atomic
    def open_dispute(
        order: Order,
        actor=None,
        reason: str = '',
        *,
        dispute_category: str = 'other',
    ) -> Order:
        """Open a formal dispute."""
        if order.status in ['cancelled', 'completed', 'disputed', 'delivered']:
            raise ValueError(f"Cannot open dispute for order in {order.status} status.")

        cat = (dispute_category or 'other').strip().lower()
        shipped_ok_categories = {'never_arrived', 'seller_unresponsive'}
        if order.status == 'arrived':
            pass
        elif order.status == 'shipped' and cat in shipped_ok_categories:
            pass
        else:
            raise ValueError(
                "Disputes about the item itself can be opened after the order is marked as arrived. "
                "If the package never arrived or the seller is unresponsive while it is in transit, "
                "open a dispute from the order screen and pick the matching reason."
            )

        prev = order.status
        with order_status_write_context(order):
            order.status = 'disputed'
            order.save(update_fields=['status', 'updated_at'])

        # 1. Fetch the engine transaction
        txn = Transaction.objects.filter(linked_order=order, status=TransactionStatus.HOLD).first()
        if not txn:
             # If transaction is already disputed in engine but not order, just sync (robustness)
             txn = Transaction.objects.filter(linked_order=order, status=TransactionStatus.DISPUTED).first()
        
        if not txn:
            raise ValueError("No active escrow transaction found to dispute.")

        if txn.status != TransactionStatus.DISPUTED:
            # Use escrow service to open engine-level dispute
            engine_open_dispute(
                txn,
                opened_by=actor,
                reason=reason,
                legacy_order=order,
            )

        # Sync Delivery
        OrderLifecycleManager._sync_delivery(order)

        write_order_audit(
            order,
            'open_dispute',
            actor=actor,
            from_status=prev,
            to_status=order.status,
            metadata={'reason': reason},
        )
        emit_event('ORDER_DISPUTE_OPENED', {'order_id': order.id}, source_module='commerce.lifecycle')
        _lifecycle_paranoia(order)
        return order

    @staticmethod
    @transaction.atomic
    def resolve_dispute(order: Order, resolution: str, actor=None, admin_notes: str = '') -> Order:
        """Resolve a dispute: refund or release funds."""
        if order.status != 'disputed':
            raise ValueError("This order is not in disputed status.")

        if resolution not in ['refund', 'release']:
            raise ValueError("Resolution must be either 'refund' or 'release'.")

        prev = order.status
        # 1. Resolve only through escrow_engine (dispute record + fund transition)
        txn = Transaction.objects.filter(linked_order=order).first()
        if not txn:
            raise ValueError('No escrow transaction is linked to this order.')
        try:
            eng_dispute = txn.dispute
        except Dispute.DoesNotExist as exc:
            raise ValueError(
                'No escrow dispute exists for this order; open a dispute in the engine first.'
            ) from exc
        escrow_svc.resolve_dispute(
            eng_dispute,
            resolution=resolution,
            admin_notes=admin_notes,
            resolved_by=actor,
        )
        if resolution == 'release':
            emit_event(
                'ESCROW_FUNDS_RELEASED',
                {'order_id': order.id, 'source': 'dispute_resolve'},
                source_module='commerce.lifecycle',
            )
        else:
            emit_event(
                'ESCROW_REFUND_APPLIED',
                {'order_id': order.id, 'source': 'dispute_resolve'},
                source_module='commerce.lifecycle',
            )

        # 2. Sync Order status
        now = timezone.now()
        with order_status_write_context(order):
            if resolution == 'refund':
                order.status = 'cancelled'
                order.cancelled_at = now
            else:
                order.status = 'completed'
                order.completed_at = now

            order.save(update_fields=['status', 'cancelled_at', 'completed_at', 'updated_at'])

            # Sync Delivery
            OrderLifecycleManager._sync_delivery(order)

            write_order_audit(
                order,
                'resolve_dispute',
                actor=actor,
                from_status=prev,
                to_status=order.status,
                metadata={'resolution': resolution, 'admin_notes': admin_notes},
            )
        emit_event(
            'ORDER_DISPUTE_RESOLVED',
            {'order_id': order.id, 'resolution': resolution},
            source_module='commerce.lifecycle',
        )
        _lifecycle_paranoia(order)
        return order

    @staticmethod
    @transaction.atomic
    def mark_arrived(order: Order, actor=None) -> Order:
        """Mark order as arrived at its destination/pickup point."""
        if order.status != 'shipped':
            raise ValueError(f"Cannot mark order as arrived from {order.status} status.")

        prev = order.status
        with order_status_write_context(order):
            now = timezone.now()
            order.status = 'arrived'
            order.arrived_at = now
            order.save(update_fields=['status', 'arrived_at', 'updated_at'])
            
            # Sync Delivery
            OrderLifecycleManager._sync_delivery(order)
            
            write_order_audit(
                order, 'mark_arrived', actor=actor, from_status=prev, to_status=order.status
            )
        emit_event('ORDER_ARRIVED', {'order_id': order.id}, source_module='commerce.lifecycle')
        _lifecycle_paranoia(order)
        return order

    @staticmethod
    @transaction.atomic
    def confirm_delivery(order: Order, actor=None) -> Order:
        """
        System / automation: mark order as delivered (buyer received goods).
        Does not release escrow — use confirm_receipt or timed release policy.
        """
        if order.status not in ['shipped', 'arrived']:
            raise ValueError(f"Cannot mark delivered from {order.status} status.")

        prev = order.status
        with order_status_write_context(order):
            now = timezone.now()
            order.status = 'delivered'
            order.delivered_at = now
            order.save(update_fields=['status', 'delivered_at', 'updated_at'])
            OrderLifecycleManager._sync_delivery(order)
            write_order_audit(
                order, 'confirm_delivery', actor=actor, from_status=prev, to_status=order.status
            )
        emit_event('ORDER_DELIVERED', {'order_id': order.id}, source_module='commerce.lifecycle')
        _lifecycle_paranoia(order)
        return order

    @staticmethod
    def _sync_delivery(order: Order, tracking_number: str = None, carrier: str = None):
        """Internal helper to keep the Delivery object in sync with Order status."""
        try:
            delivery, created = Delivery.objects.get_or_create(
                order=order,
                defaults={
                    'address_line1': order.shipping_address[:300] if order.shipping_address else 'Unknown',
                    'city': 'Unknown',
                    'recipient_name': order.buyer.get_full_name() or order.buyer.username,
                    'status': 'pending'
                }
            )
            
            # Update status from registry
            delivery.status = get_delivery_status(order.status)
            
            # Update tracking if provided or available on order
            if tracking_number:
                delivery.tracking_number = tracking_number
            elif not delivery.tracking_number and order.tracking_number:
                delivery.tracking_number = order.tracking_number
                
            if carrier:
                delivery.carrier = carrier
            elif not delivery.carrier and order.shipping_method:
                 delivery.carrier = order.shipping_method

            # Sync timestamps
            if order.shipped_at:
                delivery.shipped_at = order.shipped_at
            
            delivery.save()
            logger.info("Synchronized Delivery %s for Order %s to status %s", delivery.id, order.id, delivery.status)
        except Exception as e:
            logger.error("Failed to sync Delivery for Order %s: %s", order.id, e)
