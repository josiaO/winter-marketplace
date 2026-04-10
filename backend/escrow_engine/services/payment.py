"""
escrow_engine.services.payment
--------------------------------
Payment initiation, confirmation, and webhook processing.

Flow:
  create_transaction()       → status: CREATED
  initiate_payment()         → status: PENDING_PAYMENT  + returns payment URL
  confirm_payment() / webhook → status: PAID
  hold_funds()               → status: HOLD  (called automatically after PAID)
"""
from __future__ import annotations
import logging
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Tuple

from django.db import IntegrityError
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from escrow_engine.models import Transaction, GatewayEvent
from escrow_engine.providers import get_provider
from escrow_engine.providers.base import PaymentResult
from escrow_engine.state_machine import TransactionStatus, PaymentConfirmationSource
from escrow_engine.models import PaymentRecord
from escrow_engine.services.escrow import hold_funds
from escrow_engine.services.payment_records import write_payment_record
from escrow_engine.services.metrics_log import log_escrow_metric, log_escrow_failure
from escrow_engine.services.webhook_ids import extract_webhook_event_id
from escrow_engine.services.distributed_lock import escrow_distributed_lock
from escrow_engine import prometheus_metrics as prom
from escrow_engine.utils import scrub_gateway_payload

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _transaction_for_webhook_audit(
    gateway_ref,
    order_id,
) -> Optional[Transaction]:
    """Resolve a transaction for logging only (no row lock)."""
    if gateway_ref:
        txn = Transaction.objects.filter(gateway_reference=gateway_ref).first()
        if txn:
            return txn
        txn = Transaction.objects.filter(pk=gateway_ref).first()
        if txn:
            return txn
    if order_id is not None:
        return Transaction.objects.filter(linked_order__id=order_id).first()
    return None


def upsert_gateway_webhook_event(
    provider: str,
    gateway_data: dict,
) -> Tuple[GatewayEvent, bool]:
    """
    Persist webhook payload for idempotency. Returns (row, created).
    """
    event_id = extract_webhook_event_id(provider, gateway_data)
    try:
        with db_transaction.atomic():
            ge = GatewayEvent.objects.create(
                provider=provider,
                event_id=event_id,
                payload=scrub_gateway_payload(gateway_data),
                status=GatewayEvent.Status.PENDING,
            )
            return ge, True
    except IntegrityError:
        ge = GatewayEvent.objects.get(provider=provider, event_id=event_id)
        return ge, False


def execute_webhook_for_stored_event(ge: GatewayEvent) -> Transaction | None:
    """
    Run provider verification and confirmation for a stored GatewayEvent.
    Uses a distributed lock per (provider, event_id).
    """
    if ge.status in (
        GatewayEvent.Status.PROCESSED,
        GatewayEvent.Status.DUPLICATE,
    ):
        prom.escrow_webhook_duplicate_total.inc()
        return ge.transaction

    if ge.status == GatewayEvent.Status.FAILED:
        return ge.transaction

    lock_key = f'escrow:webhook:{ge.provider}:{ge.event_id}'
    with escrow_distributed_lock(lock_key) as acquired:
        if not acquired:
            log_escrow_failure(
                'escrow.failure',
                'webhook lock not acquired',
                severity='critical',
                provider=ge.provider,
                event_id=ge.event_id,
            )
            return ge.transaction

        ge.refresh_from_db()
        if ge.status in (
            GatewayEvent.Status.PROCESSED,
            GatewayEvent.Status.DUPLICATE,
            GatewayEvent.Status.FAILED,
        ):
            prom.escrow_webhook_duplicate_total.inc()
            return ge.transaction

        return _execute_webhook_core(ge)


def handle_webhook(gateway_data: dict, payment_method: str = 'selcom') -> Transaction | None:
    """
    Process an incoming payment gateway webhook (backward-compatible entrypoint).

    Persists GatewayEvent, deduplicates by provider event_id, then confirms payment if valid.
    """
    provider_name = payment_method or 'selcom'
    ge, _created = upsert_gateway_webhook_event(provider_name, gateway_data)
    return execute_webhook_for_stored_event(ge)


def _mark_ge(
    ge: GatewayEvent,
    *,
    status: str,
    transaction: Transaction | None = None,
    error_message: str = '',
) -> None:
    now = timezone.now()
    with db_transaction.atomic():
        GatewayEvent.objects.filter(pk=ge.pk).update(
            status=status,
            transaction=transaction,
            processed_at=now,
            error_message=(error_message or '')[:2000],
        )
    ge.status = status
    ge.transaction = transaction
    ge.processed_at = now
    ge.error_message = (error_message or '')[:2000]


def _execute_webhook_core(ge: GatewayEvent) -> Transaction | None:
    payment_method = ge.provider
    gateway_data = ge.payload or {}
    provider = get_provider(payment_method)
    result = provider.verify_payment(gateway_data)

    gateway_ref = result.gateway_reference
    order_id = gateway_data.get('order_id')

    if not result.success:
        logger.warning("Webhook verification failed: %s", result.error)
        txn_loose = _transaction_for_webhook_audit(gateway_ref, order_id)
        write_payment_record(
            transaction=txn_loose,
            provider=payment_method,
            amount=txn_loose.amount if txn_loose else Decimal('0'),
            currency=txn_loose.currency if txn_loose else 'TZS',
            status=PaymentRecord.Status.FAILED,
            reference=str(gateway_ref or '') or '',
            raw_payload=gateway_data,
            failure_reason=(result.error or '')[:2000] or 'webhook_verify_failed',
        )
        log_escrow_metric(
            'escrow.webhook.verify_failed',
            gateway_reference=str(gateway_ref or ''),
            reference=getattr(txn_loose, 'reference', '') or '',
        )
        prom.escrow_payments_failed_total.labels(stage='webhook_verify').inc()
        _mark_ge(ge, status=GatewayEvent.Status.FAILED, transaction=txn_loose, error_message=result.error or '')
        return None

    with db_transaction.atomic():
        txn = Transaction.objects.select_for_update().filter(
            gateway_reference=gateway_ref
        ).first()
        if txn is None:
            txn = Transaction.objects.select_for_update().filter(pk=gateway_ref).first()
        if txn is None and order_id is not None:
            txn = Transaction.objects.select_for_update().filter(
                linked_order__id=order_id
            ).first()

        if not txn:
            logger.error(
                "Webhook: No transaction found for gateway_reference=%s",
                gateway_ref,
            )
            write_payment_record(
                transaction=None,
                provider=payment_method,
                amount=Decimal('0'),
                currency='TZS',
                status=PaymentRecord.Status.FAILED,
                reference=str(gateway_ref or '') or '',
                raw_payload=gateway_data,
                failure_reason='webhook_unknown_transaction',
            )
            _mark_ge(ge, status=GatewayEvent.Status.FAILED, error_message='unknown_transaction')
            prom.escrow_payments_failed_total.labels(stage='webhook_unknown_txn').inc()
            return None

        if txn.status not in (TransactionStatus.CREATED, TransactionStatus.PENDING_PAYMENT):
            logger.info(
                "Webhook: Transaction %s already in status %s — ignoring duplicate.",
                txn.reference,
                txn.status,
            )
            ref_s = str(gateway_ref or '')
            recent_dup = PaymentRecord.objects.filter(
                transaction=txn,
                failure_reason='webhook_idempotent_duplicate',
                reference=ref_s,
                created_at__gte=timezone.now() - timedelta(hours=1),
            ).exists()
            if not recent_dup:
                write_payment_record(
                    transaction=txn,
                    provider=payment_method,
                    amount=txn.amount,
                    currency=txn.currency,
                    status=PaymentRecord.Status.FAILED,
                    reference=ref_s,
                    raw_payload=result.raw_payload or {},
                    failure_reason='webhook_idempotent_duplicate',
                )
            log_escrow_metric('escrow.webhook.duplicate', reference=txn.reference, status=txn.status)
            prom.escrow_webhook_duplicate_total.inc()
            _mark_ge(ge, status=GatewayEvent.Status.DUPLICATE, transaction=txn)
            return txn

    log_escrow_metric('escrow.webhook.confirming', reference=txn.reference)

    txn = confirm_payment(
        txn,
        gateway_reference=gateway_ref,
        raw_payload=result.raw_payload,
        confirmation_source=PaymentConfirmationSource.WEBHOOK,
    )
    prom.escrow_payments_success_total.inc()
    _mark_ge(ge, status=GatewayEvent.Status.PROCESSED, transaction=txn)
    return txn


def initiate_payment(
    transaction: Transaction,
    *,
    actor=None,
    payment_method: str = '',
    buyer_phone: str = '',
    buyer_name: str = '',
    payment_channel: str = '',
    redirect_url: str = '',
    cancel_url: str = '',
    idempotency_key: str = '',
    **kwargs,
) -> PaymentResult:
    """
    Move transaction to PENDING_PAYMENT and ask the gateway to start payment.
    Returns a PaymentResult containing the payment_url for redirect.

    Optional ``idempotency_key`` (or ``idempotency_key`` in ``kwargs``): when
    repeated with the same key after a successful checkout creation, returns the
    stored checkout URL / gateway reference without calling the provider again.

    Works for all three channels:
      marketplace → buyer_phone from SellerProfile or checkout form
      external    → buyer_phone from PaymentLink flow
      api         → caller supplies buyer info
    """
    idem_raw = idempotency_key or kwargs.pop('idempotency_key', '') or ''
    idem = idem_raw.strip() or None

    transaction.refresh_from_db()
    meta = dict(transaction.metadata or {})
    if (
        idem
        and meta.get('payment_idempotency_key') == idem
        and transaction.status == TransactionStatus.PENDING_PAYMENT
        and transaction.gateway_reference
    ):
        log_escrow_metric(
            'escrow.payment.initiate_idempotent',
            reference=transaction.reference,
            idempotency_key=idem,
        )
        return PaymentResult(
            success=True,
            payment_url=meta.get('payment_checkout_url', ''),
            gateway_reference=transaction.gateway_reference,
            raw_payload=meta.get('payment_idempotency_payload') or {},
        )

    method = payment_method or transaction.payment_method or 'selcom'
    provider = get_provider(method)

    if transaction.status == TransactionStatus.CREATED:
        transaction.transition_to(
            TransactionStatus.PENDING_PAYMENT,
            actor=actor,
            reason='Payment initiated',
        )

    # Update payment method on transaction if provided
    if payment_method and payment_method != transaction.payment_method:
        Transaction.objects.filter(pk=transaction.pk).update(payment_method=method)
        transaction.payment_method = method

    channel = payment_channel or payment_method or method
    result = provider.initiate_payment(
        transaction,
        buyer_phone=buyer_phone,
        buyer_name=buyer_name,
        payment_channel=channel,
        redirect_url=redirect_url,
        cancel_url=cancel_url,
        **kwargs,
    )

    if result.success and result.gateway_reference:
        Transaction.objects.filter(pk=transaction.pk).update(
            gateway_reference=result.gateway_reference,
            gateway_payload=scrub_gateway_payload(result.raw_payload),
        )
        transaction.gateway_reference = result.gateway_reference

    if result.success and idem and result.gateway_reference:
        meta = dict(transaction.metadata or {})
        meta['payment_idempotency_key'] = idem
        meta['payment_checkout_url'] = result.payment_url or ''
        meta['payment_idempotency_payload'] = result.raw_payload or {}
        Transaction.objects.filter(pk=transaction.pk).update(metadata=meta)
        transaction.metadata = meta

    # Development convenience: when the provider is running in mock mode (no API keys),
    # immediately confirm payment so the order/escrow is marked as PAID→HOLD.
    # Real providers will instead confirm via webhook.
    try:
        if (
            settings.DEBUG
            and result.success
            and isinstance(result.raw_payload, dict)
            and result.raw_payload.get('mock') is True
            and transaction.status == TransactionStatus.PENDING_PAYMENT
        ):
            confirm_payment(
                transaction,
                gateway_reference=result.gateway_reference or transaction.gateway_reference,
                raw_payload=result.raw_payload,
                actor=actor,
                confirmation_source=PaymentConfirmationSource.DEV_MOCK,
            )
    except Exception:
        # Never break checkout because of the dev-only auto-confirm.
        logger.exception("Dev auto-confirm payment failed for %s", transaction.reference)

    if not result.success:
        logger.error(
            "Payment initiation failed for %s via %s: %s",
            transaction.reference, method, result.error,
        )
        prom.escrow_payments_failed_total.labels(stage='initiate').inc()
        log_escrow_failure(
            'escrow.failure',
            'payment initiation failed',
            severity='critical',
            reference=transaction.reference,
            method=method,
            error=str(result.error or '')[:500],
        )

    initiated_by = actor if getattr(actor, 'is_authenticated', False) else None
    write_payment_record(
        transaction=transaction,
        provider=method,
        amount=transaction.amount,
        currency=transaction.currency,
        status=(
            PaymentRecord.Status.COMPLETED
            if result.success
            else PaymentRecord.Status.FAILED
        ),
        reference=result.gateway_reference or '',
        raw_payload=result.raw_payload,
        failure_reason=result.error or '',
        initiated_by=initiated_by,
    )

    log_escrow_metric(
        'escrow.payment.initiate',
        reference=transaction.reference,
        success=result.success,
        method=method,
        idempotency_key=idem or '',
    )

    return result


def sync_buyer_contact_for_checkout(
    transaction: Transaction,
    *,
    buyer_email: str = '',
    buyer_phone: str = '',
) -> Transaction:
    """
    Persist buyer email/phone on the Transaction for gateway checkout (party metadata only).

    Source of Truth: escrow_engine owns all Transaction row writes; commerce must not use
    Transaction.objects.update(...) for this. This helper never changes payment status.
    """
    updates = {}
    email = (buyer_email or '').strip()
    phone = (buyer_phone or '').strip()
    if email and not (transaction.buyer_email or '').strip():
        updates['buyer_email'] = email
    if phone and not (transaction.buyer_phone or '').strip():
        updates['buyer_phone'] = phone
    if not updates:
        return transaction
    Transaction.objects.filter(pk=transaction.pk).update(**updates)
    transaction.refresh_from_db()
    return transaction


def verify_payment_with_provider(transaction: Transaction) -> PaymentResult:
    """
    Confirm payment eligibility using provider APIs and/or engine state — never the client.

    Idempotent: if the transaction already left the unpaid states, returns success so callers
    can align order state without re-querying the gateway.
    """
    transaction.refresh_from_db()
    settled = {
        TransactionStatus.PAID,
        TransactionStatus.HOLD,
        TransactionStatus.RELEASED,
        TransactionStatus.REFUNDED,
        TransactionStatus.DISPUTED,
    }
    if transaction.status in settled:
        return PaymentResult(
            success=True,
            gateway_reference=transaction.gateway_reference or '',
            raw_payload={'verified_by': 'engine_state', 'status': transaction.status},
        )

    if transaction.status not in (TransactionStatus.CREATED, TransactionStatus.PENDING_PAYMENT):
        return PaymentResult(
            success=False,
            error=f'payment_verification_not_applicable_status_{transaction.status}',
            gateway_reference=transaction.gateway_reference or '',
            raw_payload={},
        )

    method = transaction.payment_method or 'selcom'
    provider = get_provider(method, transaction=transaction)
    return provider.query_payment_status(transaction)


def verify_payment_status(transaction: Transaction) -> bool:
    """True if provider (or engine state) confirms payment success."""
    return verify_payment_with_provider(transaction).success


def confirm_payment(
    transaction: Transaction,
    *,
    gateway_reference: str = '',
    raw_payload: dict = None,
    actor=None,
    confirmation_source: str,
) -> Transaction:
    """
    Mark a transaction as PAID and immediately move it to HOLD.

    ``confirmation_source`` is mandatory — every path into PAID/HOLD must be auditable.
    PROVIDER_VERIFY requires ``raw_payload['provider_verify']`` from server-side gateway checks.
    """
    allowed = {
        PaymentConfirmationSource.WEBHOOK,
        PaymentConfirmationSource.PROVIDER_VERIFY,
        PaymentConfirmationSource.ADMIN_MANUAL,
        PaymentConfirmationSource.DEV_MOCK,
    }
    if confirmation_source not in allowed:
        raise ValueError(f'Invalid confirmation_source: {confirmation_source!r}')

    payload = raw_payload if raw_payload is not None else {}
    if confirmation_source == PaymentConfirmationSource.PROVIDER_VERIFY:
        if not isinstance(payload, dict) or not payload.get('provider_verify'):
            raise ValueError(
                'Unverified confirmation attempt: PROVIDER_VERIFY requires '
                'raw_payload["provider_verify"] from verify_payment_with_provider.'
            )
    if confirmation_source == PaymentConfirmationSource.WEBHOOK:
        gw = (gateway_reference or '').strip()
        if not gw and not (isinstance(payload, dict) and payload):
            raise ValueError(
                'Unverified confirmation attempt: WEBHOOK requires gateway_reference '
                'or non-empty raw_payload from the gateway.'
            )

    with db_transaction.atomic():
        txn = Transaction.objects.select_for_update().get(pk=transaction.pk)

        if gateway_reference:
            Transaction.objects.filter(pk=txn.pk).update(
                gateway_reference=gateway_reference,
                gateway_payload=scrub_gateway_payload(payload),
            )
            txn.refresh_from_db()

        if txn.status in (TransactionStatus.CREATED, TransactionStatus.PENDING_PAYMENT):
            txn.transition_to(
                TransactionStatus.PAID,
                actor=actor,
                reason='Payment confirmed',
            )
        else:
            logger.info(
                "Skipping PAID transition for transaction %s; current status is %s",
                txn.reference,
                txn.status,
            )

        txn = hold_funds(
            txn,
            actor=actor,
            reason='Auto-hold after payment confirmation',
        )

        write_payment_record(
            transaction=txn,
            provider=txn.payment_method or 'selcom',
            amount=txn.amount,
            currency=txn.currency,
            status=PaymentRecord.Status.COMPLETED,
            reference=gateway_reference or txn.gateway_reference or '',
            raw_payload=payload,
            failure_reason='',
            initiated_by=actor if getattr(actor, 'is_authenticated', False) else None,
        )

        meta = dict(txn.metadata or {})
        meta['payment_confirmation_source'] = confirmation_source
        meta['payment_confirmation_at'] = timezone.now().isoformat()
        Transaction.objects.filter(pk=txn.pk).update(metadata=meta)
        txn.metadata = meta

    prom.escrow_transactions_total.labels(source=str(txn.source or 'unknown')).inc()
    log_escrow_metric('escrow.payment.confirmed', reference=txn.reference)
    logger.info("Payment confirmed and funds held for transaction %s", txn.reference)
    return txn
