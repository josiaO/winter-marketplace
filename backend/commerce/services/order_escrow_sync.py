"""
Align commerce.Order with escrow_engine outcomes (commerce-owned rows only).

Source of Truth: escrow_engine mutates Transaction; commerce owns Order.status.
These helpers apply order-side updates after financial transitions and must run
inside order_status_write_context(order) so Order.save() guards accept them.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from commerce.models import Order
from commerce.services.order_mutations import order_status_write_context
from escrow_engine.models import Transaction

logger = logging.getLogger(__name__)


def sync_marketplace_order_on_escrow_hold(transaction: Transaction) -> None:
    """After funds hit HOLD, move linked marketplace order from pending toward confirmed."""
    if not transaction.linked_order_id:
        logger.warning('Sync skip: Transaction %s has no linked_order_id', transaction.reference)
        return
    try:
        order = Order.objects.get(pk=transaction.linked_order_id)
        if order.status == 'confirmed':
            logger.info('Sync redundant: Order %s already confirmed', order.id)
            return
        now = timezone.now()
        with order_status_write_context(order):
            order.status = 'confirmed'
            order.confirmed_at = now
            order.save(update_fields=['status', 'confirmed_at', 'updated_at'])
        logger.info(
            'Synced order %s to confirmed after escrow HOLD for %s',
            order.id,
            transaction.reference,
        )
    except Exception as exc:
        logger.error(
            'Could not sync order to confirmed for order %s: %s',
            transaction.linked_order_id,
            exc,
            exc_info=True,
        )


def sync_marketplace_order_on_escrow_release(transaction: Transaction) -> None:
    """After RELEASED, mark linked marketplace order completed when appropriate."""
    if not transaction.linked_order_id:
        return
    try:
        order = Order.objects.get(pk=transaction.linked_order_id)
        if order.status == 'completed':
            return
        now = timezone.now()
        with order_status_write_context(order):
            order.status = 'completed'
            order.completed_at = now
            order.save(update_fields=['status', 'completed_at', 'updated_at'])
    except Exception as exc:
        logger.warning(
            'Could not sync order status to completed for order %s: %s',
            transaction.linked_order_id,
            exc,
        )


def sync_marketplace_order_on_escrow_refund(transaction: Transaction) -> None:
    """After REFUNDED, mark linked marketplace order cancelled."""
    if not transaction.linked_order_id:
        return
    try:
        order = Order.objects.get(pk=transaction.linked_order_id)
        if order.status == 'cancelled':
            return
        now = timezone.now()
        with order_status_write_context(order):
            order.status = 'cancelled'
            order.cancelled_at = now
            order.save(update_fields=['status', 'cancelled_at', 'updated_at'])
    except Exception as exc:
        logger.warning(
            'Could not sync order status to cancelled for order %s: %s',
            transaction.linked_order_id,
            exc,
        )
def sync_marketplace_order_on_escrow_dispute(transaction: Transaction) -> None:
    """After DISPUTED, mark linked marketplace order as disputed."""
    if not transaction.linked_order_id:
        return
    try:
        order = Order.objects.get(pk=transaction.linked_order_id)
        if order.status == 'disputed':
            return
        with order_status_write_context(order):
            order.status = 'disputed'
            order.save(update_fields=['status', 'updated_at'])
        logger.info(
            'Synced order %s to disputed after escrow DISPUTE for %s',
            order.id,
            transaction.reference,
        )
    except Exception as exc:
        logger.warning(
            'Could not sync order status to disputed for order %s: %s',
            transaction.linked_order_id,
            exc,
        )
