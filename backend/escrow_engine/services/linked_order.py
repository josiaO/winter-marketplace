"""
Read-side guards for commerce.Order ↔ escrow_engine.Transaction links.

Commerce schedules and lifecycle code uses this module to *observe* escrow state
without duplicating payment authority (all mutations stay in escrow services).
"""
from __future__ import annotations

from escrow_engine.models import Transaction
from escrow_engine.state_machine import TransactionStatus

_STATUSES_SKIP_UNPAID_CANCEL = (
    TransactionStatus.PAID,
    TransactionStatus.HOLD,
    TransactionStatus.RELEASED,
    TransactionStatus.DISPUTED,
    TransactionStatus.REFUNDED,
)


def linked_order_has_escrow_payment_activity(order) -> bool:
    """
    True when the order's linked transaction has left the unpaid checkout funnel.

    Used by commerce tasks so auto-cancel matches the same policy as the
    cancel worker (PAID/HOLD/RELEASED/DISPUTED/REFUNDED all imply money or a
    dispute was already materialized in the engine).
    """
    return Transaction.objects.filter(
        linked_order=order,
        status__in=_STATUSES_SKIP_UNPAID_CANCEL,
    ).exists()
