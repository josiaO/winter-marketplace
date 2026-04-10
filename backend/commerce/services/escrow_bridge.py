"""
Commerce → escrow_engine calls with preconditions (avoid invalid cross-domain moves).

Source of Truth: money transitions still execute inside escrow_engine.services.escrow;
this module only validates linked Transaction state before delegating.
"""
from __future__ import annotations

from escrow_engine.models import Transaction, TransactionStatus
import escrow_engine.services.escrow as escrow_svc


def _txn_for_order(order) -> Transaction | None:
    if not order or not order.pk:
        return None
    return Transaction.objects.filter(linked_order=order).first()


def safe_hold_funds_for_order(
    order,
    *,
    actor=None,
    actor_label: str = '',
    reason: str = '',
) -> Transaction | None:
    txn = _txn_for_order(order)
    if not txn:
        return None
    if txn.status == TransactionStatus.HOLD:
        return txn
    # Engine hold is only valid from PAID (see state machine).
    if txn.status != TransactionStatus.PAID:
        return None
    return escrow_svc.hold_funds(
        txn,
        actor=actor,
        actor_label=actor_label or 'System',
        reason=reason or 'Hold funds',
    )


def safe_release_funds_for_order(
    order,
    *,
    actor=None,
    actor_label: str = '',
    reason: str = '',
) -> Transaction:
    txn = _txn_for_order(order)
    if not txn:
        raise ValueError(f'No escrow transaction linked to order {order.pk}.')
    if txn.status != TransactionStatus.HOLD:
        raise ValueError(
            f'Cannot release: order {order.pk} escrow is {txn.status}, expected HOLD.'
        )
    return escrow_svc.release_funds(
        txn,
        actor=actor,
        actor_label=actor_label or 'User',
        reason=reason or 'Release funds',
    )


def safe_refund_funds_for_order(
    order,
    *,
    actor=None,
    actor_label: str = '',
    reason: str = '',
) -> Transaction | None:
    txn = _txn_for_order(order)
    if not txn:
        return None
    if txn.status not in (
        TransactionStatus.PAID,
        TransactionStatus.HOLD,
        TransactionStatus.DISPUTED,
    ):
        raise ValueError(
            f'Cannot refund: order {order.pk} escrow is {txn.status}.'
        )
    return escrow_svc.refund_funds(
        txn,
        actor=actor,
        actor_label=actor_label or 'System',
        reason=reason or 'Refund',
    )
