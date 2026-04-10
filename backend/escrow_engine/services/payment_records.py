"""
Append-only PaymentRecord rows for gateway / payment audit trail.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from escrow_engine.models import PaymentRecord, Transaction


def write_payment_record(
    *,
    transaction: Optional[Transaction],
    provider: str,
    amount: Decimal,
    currency: str,
    status: str,
    reference: str = '',
    raw_payload: Optional[dict[str, Any]] = None,
    failure_reason: str = '',
    initiated_by=None,
) -> PaymentRecord:
    return PaymentRecord.objects.create(
        transaction=transaction,
        provider=provider or 'selcom',
        amount=amount,
        currency=currency or 'TZS',
        status=status,
        reference=reference or '',
        raw_payload=raw_payload if raw_payload is not None else {},
        failure_reason=failure_reason or '',
        initiated_by=initiated_by,
    )
