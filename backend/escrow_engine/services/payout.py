"""
escrow_engine.services.payout
-------------------------------
Seller payout creation and processing.
"""
from __future__ import annotations
import logging
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from escrow_engine.models import Transaction, Payout, PayoutDestination
from escrow_engine.providers import get_provider
from escrow_engine.providers.base import PaymentResult
from escrow_engine.services.metrics_log import log_escrow_metric, log_escrow_failure
from escrow_engine.services.distributed_lock import escrow_distributed_lock
from escrow_engine import prometheus_metrics as prom
from escrow_engine.state_machine import TransactionStatus

logger = logging.getLogger(__name__)


def create_payout(transaction: Transaction, *, payout_method: str = 'mpesa') -> Payout:
    """
    Create a Payout record for the seller after escrow is released.

    Called automatically by release_funds().
    Idempotent — returns existing payout if already created.
    """
    with db_transaction.atomic():
        txn = (
            Transaction.objects.select_for_update()
            .select_related('linked_order')
            .get(pk=transaction.pk)
        )

        if txn.status != TransactionStatus.RELEASED:
            raise ValueError(
                f"Cannot create payout for transaction in status {txn.status}. "
                "Transaction must be RELEASED."
            )

        if not txn.seller_user_id:
            logger.warning(
                "Cannot create payout for transaction %s — no seller_user set.",
                txn.reference,
            )
            return None

        destination = PayoutDestination.objects.filter(
            user=txn.seller_user,
            is_default=True,
        ).first()

        payout, created = Payout.objects.get_or_create(
            transaction=txn,
            defaults={
                'seller': txn.seller_user,
                'amount': _calculate_payout_amount(txn),
                'currency': txn.currency,
                'payout_method': destination.method if destination else payout_method,
                'status': Payout.Status.PENDING,
            },
        )

        if created:
            logger.info(
                "Payout created for transaction %s: %s %s → seller=%s",
                txn.reference,
                payout.amount,
                payout.currency,
                txn.seller_user.username,
            )
        return payout


def process_payout(payout: Payout, account_number: str = None, account_name: str = None, bank_code: str = None) -> Payout:
    """
    Trigger actual disbursement via the payment provider.
    Uses PayoutDestination if account details are not provided.

    Row is moved to PROCESSING before the HTTP call so concurrent workers do not
    double-disburse; the HTTP call runs outside any DB transaction.
    """
    lock_key = f'escrow:payout:{payout.pk}'
    with escrow_distributed_lock(lock_key, ttl_sec=300, blocking_timeout=15.0) as acquired:
        if not acquired:
            log_escrow_failure(
                'escrow.failure',
                'payout lock not acquired',
                severity='critical',
                payout_id=payout.pk,
            )
            return Payout.objects.get(pk=payout.pk)

        return _process_payout_locked(
            payout,
            account_number=account_number,
            account_name=account_name,
            bank_code=bank_code,
        )


def _process_payout_locked(
    payout: Payout,
    account_number: str = None,
    account_name: str = None,
    bank_code: str = None,
) -> Payout:
    with prom.escrow_payout_latency_seconds.time():
        with db_transaction.atomic():
            payout = (
                Payout.objects.select_related('transaction')
                .select_for_update()
                .get(pk=payout.pk)
            )
            txn = payout.transaction

            if payout.status == Payout.Status.PROCESSING:
                log_escrow_metric(
                    'escrow.payout.skip_processing',
                    payout_id=payout.pk,
                    reference=payout.transaction.reference,
                )
                return payout

            if payout.status not in (Payout.Status.PENDING, Payout.Status.FAILED):
                raise ValueError(
                    f"Payout {payout.pk} is in status {payout.status} — cannot process."
                )

            if not account_number:
                destination = PayoutDestination.objects.filter(
                    user=payout.seller,
                    method=payout.payout_method,
                ).first()
                if not destination:
                    payout.status = Payout.Status.FAILED
                    payout.failure_reason = "No payout destination found for seller."
                    payout.save()
                    try:
                        from core.events import emit_event

                        emit_event(
                            'PAYOUT_PROCESSING_FAILED',
                            {
                                'payout_id': payout.pk,
                                'order_id': txn.linked_order_id,
                                'transaction_reference': txn.reference,
                                'error': payout.failure_reason,
                            },
                            source_module='escrow_engine.payout',
                        )
                    except Exception:
                        logger.debug(
                            'emit PAYOUT_PROCESSING_FAILED skipped', exc_info=True
                        )
                    return payout
                account_number = destination.account_number
                account_name = destination.account_name
                bank_code = destination.bank_code

            payout.status = Payout.Status.PROCESSING
            payout.save(update_fields=['status', 'updated_at'])

            method = payout.payout_method
            pay_amount = Decimal(str(payout.amount))

        provider = get_provider(method)
        try:
            result = provider.disburse(
                txn,
                account_number,
                account_name,
                bank_code,
                amount=pay_amount,
            )
        except Exception as exc:
            logger.exception("Payout %s disburse exception: %s", payout.pk, exc)
            result = PaymentResult(success=False, error=str(exc))

        now = timezone.now()
        with db_transaction.atomic():
            payout = Payout.objects.select_for_update().get(pk=payout.pk)
            if payout.status != Payout.Status.PROCESSING:
                log_escrow_metric(
                    'escrow.payout.concurrent_finish',
                    payout_id=payout.pk,
                    status=payout.status,
                )
                return payout

            payout.processed_at = now
            if result.success:
                payout.status = Payout.Status.COMPLETED
                payout.payout_reference = result.gateway_reference
                payout.completed_at = now
                payout.failure_reason = ''
                logger.info("Payout %s completed: ref=%s", payout.pk, result.gateway_reference)
                log_escrow_metric(
                    'escrow.payout.completed',
                    payout_id=payout.pk,
                    reference=txn.reference,
                    gateway_reference=result.gateway_reference or '',
                )
            else:
                payout.status = Payout.Status.FAILED
                payout.failure_reason = result.error
                logger.error("Payout %s FAILED: %s", payout.pk, result.error)
                log_escrow_metric(
                    'escrow.payout.failed',
                    payout_id=payout.pk,
                    reference=txn.reference,
                    error=result.error or '',
                )
                try:
                    from core.events import emit_event

                    emit_event(
                        'PAYOUT_PROCESSING_FAILED',
                        {
                            'payout_id': payout.pk,
                            'order_id': txn.linked_order_id,
                            'transaction_reference': txn.reference,
                            'error': (result.error or '')[:2000],
                        },
                        source_module='escrow_engine.payout',
                    )
                except Exception:
                    logger.debug(
                        'emit PAYOUT_PROCESSING_FAILED skipped', exc_info=True
                    )

            payout.save()
            return payout


# ── Private helpers ───────────────────────────────────────────────────────────

def _calculate_payout_amount(transaction: Transaction):
    """
    Calculate seller payout by deducting the platform fee from the order subtotal.

    For transactions linked to an Order, use the order's financial breakdown.
    For non-order transactions, pay the full transaction amount (no deduction).
    """
    if transaction.linked_order_id:
        try:
            order = transaction.linked_order
            return order.subtotal - order.platform_fee
        except Exception:
            pass
    return transaction.amount
