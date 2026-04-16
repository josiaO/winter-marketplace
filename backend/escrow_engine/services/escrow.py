"""
escrow_engine.services.escrow
-------------------------------
Core escrow fund operations: hold, release, refund.
"""
from __future__ import annotations
import logging

from django.db import transaction as db_transaction
from django.utils import timezone
from escrow_engine.models import (
    Transaction,
    TransactionSource,
    Dispute,
    DisputeEvidence,
    PaymentRecord,
)
from escrow_engine.services.payment_records import write_payment_record
from escrow_engine.services.metrics_log import log_escrow_metric
from escrow_engine.state_machine import TransactionStatus
from escrow_engine.services.payout import create_payout
from escrow_engine.providers import get_provider
from escrow_engine.services.distributed_lock import escrow_distributed_lock

# Local import in handlers below to break circularity with commerce.models

logger = logging.getLogger(__name__)


def hold_funds(
    transaction: Transaction,
    *,
    actor=None,
    actor_label: str = '',
    reason: str = 'Funds held in escrow',
) -> Transaction:
    """
    Lock funds in escrow (PAID → HOLD).
    Called automatically after payment confirmation.
    """
    with db_transaction.atomic():
        txn = Transaction.objects.select_for_update().get(pk=transaction.pk)
        txn.transition_to(
            TransactionStatus.HOLD,
            actor=actor,
            actor_label=actor_label,
            reason=reason,
        )
        _post_hold_handler(txn)

    log_escrow_metric('escrow.hold', reference=txn.reference, status=txn.status)
    logger.info("Funds held for transaction %s", txn.reference)
    return txn


def release_funds(
    transaction: Transaction,
    *,
    actor=None,
    actor_label: str = '',
    reason: str = 'Funds released to seller',
) -> Transaction:
    """
    Release escrow funds to the seller (HOLD → RELEASED).

    Branches behavior based on the transaction source (Marketplace, API, etc.).
    Automatically creates a Payout record via the PayoutDestination.
    """
    with db_transaction.atomic():
        txn = Transaction.objects.select_for_update().get(pk=transaction.pk)
        txn.transition_to(
            TransactionStatus.RELEASED,
            actor=actor,
            actor_label=actor_label or 'User',
            reason=reason,
        )
        _post_release_handler(txn)

        if txn.seller_user_id:
            create_payout(txn)


    log_escrow_metric('escrow.release', reference=txn.reference, status=txn.status)
    logger.info("Funds released for transaction %s", txn.reference)
    return txn


def refund_funds(
    transaction: Transaction,
    *,
    actor=None,
    actor_label: str = '',
    reason: str = 'Funds refunded to buyer',
) -> Transaction:
    """
    Refund escrow funds to buyer (HOLD / DISPUTED → REFUNDED).
    Gateway HTTP runs outside DB transactions; a Redis distributed lock (with
    cache fallback) prevents concurrent refund attempts for the same transaction.
    """
    lock_key = f'escrow:refund:{transaction.pk}'
    with escrow_distributed_lock(lock_key, ttl_sec=180, blocking_timeout=2.0) as got_lock:
        if not got_lock:
            txn = Transaction.objects.get(pk=transaction.pk)
            if txn.status == TransactionStatus.REFUNDED:
                log_escrow_metric(
                    'escrow.refund.concurrent_skip',
                    reference=txn.reference,
                    status=txn.status,
                )
                return txn
            raise ValueError(
                'A refund is already in progress for this transaction. Retry shortly.'
            )

        return _refund_funds_locked_body(
            transaction,
            actor=actor,
            actor_label=actor_label,
            reason=reason,
        )


def _refund_funds_locked_body(
    transaction: Transaction,
    *,
    actor=None,
    actor_label: str = '',
    reason: str = 'Funds refunded to buyer',
) -> Transaction:
    with db_transaction.atomic():
        txn = Transaction.objects.select_for_update().get(pk=transaction.pk)
        if txn.status not in (TransactionStatus.HOLD, TransactionStatus.DISPUTED):
            raise ValueError(
                f'Can only refund from HOLD or DISPUTED state. Current: {txn.status}.'
            )

    if txn.gateway_reference:
        try:
            provider = get_provider(txn.payment_method or 'selcom')
            result = provider.refund(txn, reason=reason)
            write_payment_record(
                transaction=txn,
                provider=txn.payment_method or 'selcom',
                amount=txn.amount,
                currency=txn.currency,
                status=(
                    PaymentRecord.Status.COMPLETED
                    if result.success
                    else PaymentRecord.Status.FAILED
                ),
                reference=result.gateway_reference or txn.gateway_reference or '',
                raw_payload=result.raw_payload,
                failure_reason=result.error or '',
            )
            log_escrow_metric(
                'escrow.refund.gateway',
                reference=txn.reference,
                success=result.success,
                gateway_reference=txn.gateway_reference,
            )
            if not result.success:
                logger.error(
                    "Gateway refund failed for %s: %s — ABORTING status change.",
                    txn.reference,
                    result.error,
                )
                # We return the transaction in its current state (HOLD or DISPUTED)
                # but with the failed payment record written.
                return txn
        except Exception as exc:
            logger.error("Gateway refund call exception for %s: %s", txn.reference, exc)
            write_payment_record(
                transaction=txn,
                provider=txn.payment_method or 'selcom',
                amount=txn.amount,
                currency=txn.currency,
                status=PaymentRecord.Status.FAILED,
                reference=txn.gateway_reference or '',
                raw_payload={},
                failure_reason=str(exc),
            )
            log_escrow_metric(
                'escrow.refund.gateway',
                reference=txn.reference,
                success=False,
                error=str(exc),
            )

    with db_transaction.atomic():
        txn = Transaction.objects.select_for_update().get(pk=transaction.pk)
        if txn.status not in (TransactionStatus.HOLD, TransactionStatus.DISPUTED):
            log_escrow_metric(
                'escrow.refund.state_skip',
                reference=txn.reference,
                status=txn.status,
            )
            return txn
        txn.transition_to(
            TransactionStatus.REFUNDED,
            actor=actor,
            actor_label=actor_label or 'User',
            reason=reason,
        )
        _post_refund_handler(txn)

    log_escrow_metric('escrow.refund.completed', reference=txn.reference)
    logger.info("Funds refunded for transaction %s", txn.reference)
    return txn


# ── Post-Escrow Handlers (Source Branching) ──────────────────────────────────

def _post_hold_handler(transaction: Transaction) -> None:
    """
    Branch logic after funds are successfully held based on the transaction source.
    """
    if transaction.source == TransactionSource.MARKETPLACE:
        _sync_order_confirmed(transaction)
        logger.info("Marketplace source notified of funds-held for order %s", transaction.linked_order_id)

def _post_release_handler(transaction: Transaction) -> None:
    """
    Branch logic after a successful release based on the transaction source.
    """

    if transaction.source == TransactionSource.MARKETPLACE:
        # 1. Sync commerce.Order to 'completed'
        _sync_order_completed(transaction)
        
        # 2. Trigger Marketplace Seller Notification
        # (Stub for notification service)
        logger.info("Marketplace seller notified of release for order %s", transaction.linked_order_id)
        
    elif transaction.source == TransactionSource.EXTERNAL:
        # External flows (e.g. WhatsApp payment links) notify via SMS/Email
        # (SMS logic normally in notification app)
        logger.info("External (WhatsApp) seller notified for transaction %s", transaction.reference)

def _post_refund_handler(transaction: Transaction) -> None:
    """
    Branch logic after a successful refund based on the transaction source.
    """

    if transaction.source == TransactionSource.MARKETPLACE:
        _sync_order_cancelled(transaction)
        logger.info("Marketplace buyer notified of refund for order %s", transaction.linked_order_id)

def _post_dispute_handler(transaction: Transaction) -> None:
    """
    Branch logic after a successful dispute open.
    """
    if transaction.source == TransactionSource.MARKETPLACE:
        _sync_order_disputed(transaction)
        logger.info("Marketplace source notified of dispute for order %s", transaction.linked_order_id)

# ── Sync Helpers (Marketplace Specific) ────────────────────────────────────────
# Source of Truth: commerce owns Order row updates via integrations.commerce_sync;
# escrow_engine only triggers them after financial transitions.


def _sync_order_completed(transaction: Transaction) -> None:
    from escrow_engine.integrations.commerce_sync import sync_marketplace_order_on_escrow_release

    sync_marketplace_order_on_escrow_release(transaction)


def _sync_order_confirmed(transaction: Transaction) -> None:
    from escrow_engine.integrations.commerce_sync import sync_marketplace_order_on_escrow_hold

    sync_marketplace_order_on_escrow_hold(transaction)


def _sync_order_cancelled(transaction: Transaction) -> None:
    from escrow_engine.integrations.commerce_sync import sync_marketplace_order_on_escrow_refund

    sync_marketplace_order_on_escrow_refund(transaction)


def _sync_order_disputed(transaction: Transaction) -> None:
    from escrow_engine.integrations.commerce_sync import sync_marketplace_order_on_escrow_dispute

    sync_marketplace_order_on_escrow_dispute(transaction)


# ── Dispute Handling ─────────────────────────────────────────────────────────

def open_dispute(
    transaction: Transaction,
    *,
    opened_by=None,
    actor_label: str = '',
    reason: str,
    evidence_files: list = None,
    legacy_order=None,
) -> Dispute:
    """
    Open a dispute against an escrow transaction (HOLD → DISPUTED).
    """
    if not reason.strip():
        raise ValueError("Dispute reason cannot be empty.")

    with db_transaction.atomic():
        txn = Transaction.objects.select_for_update().get(pk=transaction.pk)

        if txn.status not in (TransactionStatus.HOLD, TransactionStatus.DISPUTED):
            raise ValueError(
                f"Cannot open dispute for transaction in status {txn.status}. "
                "Transaction must be in HOLD state."
            )

        # Move transaction to DISPUTED
        if txn.status == TransactionStatus.HOLD:
            txn.transition_to(
                TransactionStatus.DISPUTED,
                actor=opened_by,
                actor_label=actor_label,
                reason=f"Dispute opened: {reason[:200]}",
            )

        dispute, created = Dispute.objects.get_or_create(
            transaction=txn,
            defaults={
                'opened_by': opened_by,
                'reason': reason,
                'status': Dispute.Status.OPEN,
                'legacy_order': legacy_order,
            },
        )

    if not created:
        dispute.reason = reason
        dispute.status = Dispute.Status.OPEN
        dispute.save(update_fields=['reason', 'status', 'updated_at'])

    if evidence_files:
        for entry in evidence_files:
            file_obj, media_type, caption, submitted_by = entry
            DisputeEvidence.objects.create(
                dispute=dispute,
                file=file_obj,
                media_type=media_type,
                caption=caption,
                submitted_by=submitted_by,
            )
        dispute.evidence_images_count = dispute.evidence.filter(media_type='image').count()
        dispute.save(update_fields=['evidence_images_count'])

    _notify_dispute_opened(txn, dispute)
    _post_dispute_handler(txn)
    logger.info("Dispute opened for transaction %s", txn.reference)
    return dispute


def resolve_dispute(
    dispute: Dispute,
    *,
    resolution: str,           # 'refund' | 'release'
    admin_notes: str = '',
    resolved_by=None,
) -> Dispute:
    """
    Resolve a dispute (admin only).
    """
    if resolution not in ('refund', 'release'):
        raise ValueError("resolution must be 'refund' or 'release'.")

    if dispute.status == Dispute.Status.RESOLVED:
        raise ValueError("Dispute is already resolved.")

    transaction = dispute.transaction
    now = timezone.now()

    if resolution == 'release':
        release_funds(transaction, actor=resolved_by, reason=f"Dispute resolved: {admin_notes or 'Released to seller'}")
        resolution_type = Dispute.Resolution.RELEASE_SELLER
    else:
        refund_funds(transaction, actor=resolved_by, reason=f"Dispute resolved: {admin_notes or 'Refunded to buyer'}")
        resolution_type = Dispute.Resolution.REFUND_BUYER

    dispute.status = Dispute.Status.RESOLVED
    dispute.resolution = admin_notes or f"Resolved via {resolution}"
    dispute.resolution_type = resolution_type
    dispute.resolved_by = resolved_by
    dispute.resolved_at = now
    dispute.save()

    _notify_dispute_resolved(transaction, dispute, resolution)
    logger.info("Dispute resolved for transaction %s: %s", transaction.reference, resolution)
    return dispute


def _notify_dispute_opened(transaction: Transaction, dispute: Dispute) -> None:
    try:
        from communications.tasks import send_generic_notification_task
        if transaction.seller_user_id:
            send_generic_notification_task.delay(
                user_id=transaction.seller_user_id,
                title="Dispute Opened ⚠️",
                message=f"Dispute on transaction {transaction.reference}. Reason: {dispute.reason[:100]}",
                notification_type="dispute",
                related_object_id=str(transaction.id),
                related_object_type="transaction",
            )
        if transaction.buyer_user_id:
            send_generic_notification_task.delay(
                user_id=transaction.buyer_user_id,
                title="Dispute Opened",
                message=f"Your dispute on {transaction.reference} is under review.",
                notification_type="dispute",
                related_object_id=str(transaction.id),
                related_object_type="transaction",
            )
    except Exception as exc:
        logger.warning("Failed to send dispute-opened notifications: %s", exc)


def _notify_dispute_resolved(transaction: Transaction, dispute: Dispute, resolution: str) -> None:
    try:
        from communications.tasks import send_generic_notification_task
        msg = 'refunded to buyer' if resolution == 'refund' else 'released to seller'
        for uid in filter(None, [transaction.buyer_user_id, transaction.seller_user_id]):
            send_generic_notification_task.delay(
                user_id=uid,
                title=f"Dispute Resolved — {resolution.title()}",
                message=f"Transaction {transaction.reference}: funds have been {msg}.",
                notification_type="dispute",
                related_object_id=str(transaction.id),
                related_object_type="transaction",
            )
    except Exception as exc:
        logger.warning("Failed to send dispute-resolved notifications: %s", exc)
