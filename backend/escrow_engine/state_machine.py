"""
escrow_engine.state_machine
---------------------------
Strict finite-state-machine for the universal Transaction lifecycle.

Allowed transitions:
  CREATED          → PENDING_PAYMENT
  PENDING_PAYMENT  → PAID | FAILED | CANCELLED
  PAID             → HOLD
  HOLD             → RELEASED | REFUNDED | DISPUTED
  DISPUTED         → RELEASED | REFUNDED
  RELEASED         (terminal)
  REFUNDED         (terminal)
  FAILED           (terminal)
  CANCELLED        (terminal)
"""
from django.core.exceptions import ValidationError


from django.db import models
from django.utils.translation import gettext_lazy as _

class TransactionStatus(models.TextChoices):
    CREATED = 'CREATED', _('Created')
    PENDING_PAYMENT = 'PENDING_PAYMENT', _('Pending Payment')
    PAID = 'PAID', _('Paid')
    HOLD = 'HOLD', _('Hold')
    RELEASED = 'RELEASED', _('Released')
    REFUNDED = 'REFUNDED', _('Refunded')
    DISPUTED = 'DISPUTED', _('Disputed')
    FAILED = 'FAILED', _('Failed')
    CANCELLED = 'CANCELLED', _('Cancelled')

TRANSACTION_STATUS_CHOICES = TransactionStatus.choices


# ── Allowed transitions ───────────────────────────────────────────────────────
_TRANSITIONS: dict[str, set[str]] = {
    TransactionStatus.CREATED:         {TransactionStatus.PENDING_PAYMENT, TransactionStatus.CANCELLED},
    TransactionStatus.PENDING_PAYMENT: {TransactionStatus.PAID, TransactionStatus.FAILED, TransactionStatus.CANCELLED},
    TransactionStatus.PAID:            {TransactionStatus.HOLD},
    TransactionStatus.HOLD:            {TransactionStatus.RELEASED, TransactionStatus.REFUNDED, TransactionStatus.DISPUTED},
    TransactionStatus.DISPUTED:        {TransactionStatus.RELEASED, TransactionStatus.REFUNDED},
    TransactionStatus.RELEASED:        set(),   # terminal
    TransactionStatus.REFUNDED:        set(),   # terminal
    TransactionStatus.FAILED:          set(),   # terminal
    TransactionStatus.CANCELLED:       set(),   # terminal
}


def validate_transition(current_status: str, new_status: str) -> None:
    """Raise ValidationError if the transition is not allowed."""
    if current_status == new_status:
        return  # no-op; idempotent
    allowed = _TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ValidationError(
            f"Invalid escrow transition: {current_status} → {new_status}. "
            f"Allowed from {current_status}: {sorted(allowed) or 'none (terminal state)'}."
        )


def is_terminal(status: str) -> bool:
    return status in {
        TransactionStatus.RELEASED,
        TransactionStatus.REFUNDED,
        TransactionStatus.FAILED,
        TransactionStatus.CANCELLED,
    }


class PaymentConfirmationSource:
    """Audit trail for confirm_payment(); every confirmation must declare a source."""

    WEBHOOK = 'webhook'
    PROVIDER_VERIFY = 'provider_verify'
    ADMIN_MANUAL = 'admin_manual'
    DEV_MOCK = 'dev_mock'
