"""
Runtime order ↔ escrow consistency checks (paranoid / dev guard).

Enable with settings.ESCROW_PARANOID_MODE — keep off in CI unless you opt in.
"""
from __future__ import annotations

import logging

from django.conf import settings

from escrow_engine.state_machine import TransactionStatus as TS

logger = logging.getLogger(__name__)


def maybe_assert_order_transaction_consistency(order) -> None:
    """
    When ESCROW_PARANOID_MODE is True, detect obvious order vs engine_transaction drift.

    Skips missing txn only while order is still pending (checkout not finished).
    """
    if not getattr(settings, 'ESCROW_PARANOID_MODE', False):
        return
    if not order or not getattr(order, 'pk', None):
        return

    try:
        txn = order.engine_transaction
    except Exception:
        txn = None

    if txn is None:
        if order.status == 'pending':
            return
        msg = (
            f'Invariant: Order {order.pk} has no engine_transaction '
            f'(status={order.status!r}).'
        )
        logger.error(msg)
        raise RuntimeError(msg)

    if txn.status == TS.RELEASED and order.status not in ('completed', 'refunded'):
        msg = (
            f'Invariant: Order {order.pk} status={order.status!r} but '
            f'escrow is RELEASED.'
        )
        logger.error(msg)
        raise RuntimeError(msg)

    if txn.status in (TS.HOLD, TS.PAID) and order.status == 'cancelled':
        msg = (
            f'Invariant: Order {order.pk} is cancelled but escrow is {txn.status!r}.'
        )
        logger.error(msg)
        raise RuntimeError(msg)
