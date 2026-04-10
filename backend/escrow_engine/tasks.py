import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from .models import Transaction, Payout, GatewayEvent
from .state_machine import TransactionStatus
from .services.metrics_log import log_escrow_failure
import escrow_engine.services.escrow as escrow_svc

logger = logging.getLogger(__name__)

@shared_task(name='escrow_engine.tasks.process_auto_releases')
def process_auto_releases():
    """
    Periodic task to automatically release funds in HOLD status
    once the auto_release_at deadline has passed.
    """
    now = timezone.now()

    eligible_ids = list(
        Transaction.objects.filter(
            status=TransactionStatus.HOLD,
            auto_release_at__lte=now,
        ).values_list('pk', flat=True)
    )

    if not eligible_ids:
        return "No transactions due for auto-release."

    logger.info("Processing auto-release for %s transactions.", len(eligible_ids))

    success_count = 0
    for pk in eligible_ids:
        try:
            with db_transaction.atomic():
                txn = (
                    Transaction.objects.select_for_update(skip_locked=True)
                    .filter(
                        pk=pk,
                        status=TransactionStatus.HOLD,
                        auto_release_at__lte=now,
                    )
                    .first()
                )
                if txn is None:
                    continue
                escrow_svc.release_funds(
                    txn,
                    actor_label='System: Auto-Release Task',
                    reason='Automated release after escrow period expired.',
                )
            success_count += 1
        except Exception as exc:
            logger.error("Auto-release failed for transaction pk=%s: %s", pk, exc)

    return f"Successfully auto-released {success_count}/{len(eligible_ids)} transactions."


@shared_task(
    name='escrow_engine.tasks.process_gateway_webhook_event',
    queue='escrow_webhooks',
)
def process_gateway_webhook_event(gateway_event_uuid: str) -> str:
    """
    Background processing for stored Selcom (or other) webhook payloads.
    """
    from escrow_engine.services.payment import execute_webhook_for_stored_event

    ge = GatewayEvent.objects.filter(pk=gateway_event_uuid).first()
    if not ge:
        return 'missing_gateway_event'
    execute_webhook_for_stored_event(ge)
    return 'ok'


@shared_task(name='escrow_engine.tasks.recover_stuck_payouts')
def recover_stuck_payouts() -> str:
    """
    Mark payouts stuck in PROCESSING as FAILED so ops can retry safely.
    Selcom status polling can be added later; we avoid blind double-disburse.
    """
    minutes = int(getattr(settings, 'ESCROW_STUCK_PAYOUT_MINUTES', 30))
    cutoff = timezone.now() - timedelta(minutes=minutes)
    qs = Payout.objects.filter(
        status=Payout.Status.PROCESSING,
        updated_at__lt=cutoff,
    )
    n = 0
    for p in qs.iterator():
        updated = Payout.objects.filter(
            pk=p.pk,
            status=Payout.Status.PROCESSING,
        ).update(
            status=Payout.Status.FAILED,
            failure_reason=(
                f'Recovery: stuck in processing >{minutes}m — verify with provider '
                f'before retrying payout.'
            )[:2000],
        )
        if updated:
            n += 1
            log_escrow_failure(
                'escrow.failure',
                'stuck payout marked failed by recovery task',
                severity='critical',
                payout_id=p.pk,
                reference=p.transaction.reference,
            )
    return f'recovered_stuck_payouts={n}'


@shared_task(name='escrow_engine.tasks.release_delivered_marketplace_escrow_periodic')
def release_delivered_marketplace_escrow_periodic():
    """
    Policy-owned auto-release: HOLD → RELEASED when the linked marketplace order
    has been in *delivered* state past the buyer protection window.

    Lives in escrow_engine so timed money movement is not scheduled from commerce.
    """
    cutoff = timezone.now() - timedelta(days=7)
    eligible = Transaction.objects.filter(
        status=TransactionStatus.HOLD,
        linked_order__status='delivered',
        linked_order__delivered_at__lte=cutoff,
    )
    count = 0
    for txn in eligible:
        try:
            escrow_svc.release_funds(
                txn,
                actor_label='System: Delivered-order auto-release',
                reason='Auto-release after 7 days in delivered status.',
            )
            count += 1
        except Exception as exc:
            logger.error(
                'Auto-release failed for txn %s: %s',
                getattr(txn, 'reference', txn.pk),
                exc,
            )
    logger.info('Triggered auto escrow release for %s transactions', count)
    return count
