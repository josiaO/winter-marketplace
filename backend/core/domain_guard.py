"""
Static and runtime guards for cross-domain invariants (Source of Truth).

Use management command ``verify_commerce_invariants`` in CI to fail builds if
forbidden fields appear on commerce models.
"""
from __future__ import annotations

# Order must never store parallel payment truth; escrow_engine.Transaction owns that.
FORBIDDEN_ORDER_PAYMENT_FIELD_NAMES = frozenset(
    {
        'payment_status',
        'paid_at',
        'is_paid',
        'payment_state',
    }
)


def assert_order_model_has_no_payment_fields() -> None:
    """Raise RuntimeError if Order defines any forbidden payment-like fields."""
    from commerce.models import Order  # local import avoids app loading issues in some contexts

    defined = {f.name for f in Order._meta.get_fields()}
    bad = sorted(FORBIDDEN_ORDER_PAYMENT_FIELD_NAMES & defined)
    if bad:
        raise RuntimeError(
            f"Source of Truth violation: Order must not define payment fields {bad}. "
            "Use order.engine_transaction (escrow_engine) for money state."
        )

