"""
Server-verified payment return handling (hosted checkout redirect).

Source of Truth: escrow_engine.services.payment confirms payment and transitions
Transaction state; this module only orchestrates verify + confirm + order audit.
Never trusts client-supplied payment status — only provider / engine state.
"""
from __future__ import annotations

from escrow_engine.models import Transaction
from escrow_engine.services.payment import confirm_payment, verify_payment_with_provider
from escrow_engine.state_machine import PaymentConfirmationSource, TransactionStatus as TS
from rest_framework.exceptions import PermissionDenied, ValidationError

from commerce.services.audit import write_order_audit
from core.events import emit_event


def confirm_marketplace_payment_return(
    *,
    user,
    transaction_reference: str,
    raw_request_meta: dict | None = None,
):
    """
    Verify payment with the gateway (or accept idempotent engine state), then confirm in-engine.

    Raises ValidationError / PermissionDenied on failure. Returns updated Transaction.
    """
    ref = (transaction_reference or '').strip()
    if not ref:
        raise ValidationError({'transaction_reference': 'This field is required.'})

    txn = (
        Transaction.objects.filter(reference=ref)
        .select_related('linked_order', 'buyer_user')
        .first()
    )
    if not txn:
        raise ValidationError('Escrow transaction not found.')

    if txn.buyer_user_id and txn.buyer_user_id != user.id and not (
        user.is_staff or user.is_superuser
    ):
        raise PermissionDenied('You do not have permission to confirm this payment.')

    # Idempotent: do not re-enter confirm_payment / hold_funds (avoids duplicate
    # PaymentRecord rows when buyers poll this endpoint after checkout).
    if txn.status in (TS.HOLD, TS.RELEASED, TS.REFUNDED, TS.DISPUTED):
        return txn

    result = verify_payment_with_provider(txn)
    if not result.success:
        emit_event(
            'PAYMENT_VERIFICATION_FAILED',
            {
                'transaction_reference': ref,
                'order_id': txn.linked_order_id,
                'error': (result.error or '')[:2000],
            },
            source_module='commerce.payment_return',
        )
        raise ValidationError(
            result.error or 'Payment could not be verified with the payment provider.'
        )

    gateway_reference = (result.gateway_reference or txn.gateway_reference or '').strip()
    payload = {
        'provider_verify': result.raw_payload or {},
        'return_meta': raw_request_meta or {},
    }
    # Source of Truth: escrow_engine owns payment confirmation (PAID/HOLD).
    txn = confirm_payment(
        txn,
        gateway_reference=gateway_reference,
        raw_payload=payload,
        actor=user,
        confirmation_source=PaymentConfirmationSource.PROVIDER_VERIFY,
    )

    if txn.linked_order_id:
        from commerce.models import Order

        order = Order.objects.get(pk=txn.linked_order_id)
        write_order_audit(
            order,
            'payment_confirmed_return',
            actor=user,
            from_status='pending',
            to_status=order.status,
            metadata={'transaction_reference': ref, 'gateway_reference': gateway_reference},
        )
        emit_event(
            'PAYMENT_CONFIRMED',
            {
                'order_id': order.id,
                'transaction_reference': ref,
                'gateway_reference': gateway_reference,
            },
            source_module='commerce.payment_return',
        )

    return txn
