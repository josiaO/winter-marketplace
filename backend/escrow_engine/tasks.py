import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from .models import Transaction, Payout, GatewayEvent, Dispute
from .state_machine import TransactionStatus, DisputeStatus
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
    eligible_ids = list(Transaction.objects.filter(
        status=TransactionStatus.HOLD,
        linked_order__status='delivered',
        linked_order__delivered_at__lte=cutoff,
    ).values_list('pk', flat=True))
    
    count = 0
    for pk in eligible_ids:
        try:
            with db_transaction.atomic():
                txn = (
                    Transaction.objects.select_for_update(skip_locked=True)
                    .filter(pk=pk, status=TransactionStatus.HOLD)
                    .first()
                )
                if not txn:
                    continue
                
                escrow_svc.release_funds(
                    txn,
                    actor_label='System: Delivered-order auto-release',
                    reason='Auto-release after 7 days in delivered status.',
                )
                count += 1
        except Exception as exc:
            logger.error(
                'Auto-release failed for txn %s: %s',
                pk,
                exc,
            )
    logger.info('Triggered auto escrow release for %s transactions', count)
    return count
@shared_task(name='escrow_engine.tasks.auto_resolve_unresponsive_seller_disputes_periodic')
def auto_resolve_unresponsive_seller_disputes_periodic():
    """
    Protects buyers from unresponsive sellers.
    1. At 24h: Sends a FINAL WARNING to the seller if they haven't uploaded evidence.
    2. At 48h: Auto-refunds the buyer if no seller response is found.
    """
    # Using top-level imports
    from .services import escrow as escrow_svc
    from communications.models import Notification
    
    now = timezone.now()
    warning_cutoff = now - timedelta(hours=24)
    resolution_cutoff = now - timedelta(hours=48)
    
    # ── 1. Auto-Resolution (48h) ──────────────────────────────────────────────
    unresponsive_disputes = Dispute.objects.filter(
        status=DisputeStatus.OPEN,
        created_at__lte=resolution_cutoff
    ).select_related('transaction')
    
    refund_count = 0
    for dispute in unresponsive_disputes:
        seller = dispute.transaction.seller_user
        # Check if seller has provided any evidence
        seller_evidence_exists = dispute.evidence.filter(submitted_by=seller).exists()
        
        if not seller_evidence_exists:
            try:
                with db_transaction.atomic():
                    # We reload to ensure it's still OPEN
                    d = Dispute.objects.select_for_update().get(pk=dispute.pk)
                    if d.status != DisputeStatus.OPEN:
                        continue
                        
                    escrow_svc.refund_funds(
                        d.transaction,
                        actor_label='System: Auto-Resolution',
                        reason=f'Seller failed to respond within 48-hour dispute window. Dispute ID: {d.id}'
                    )
                    d.status = DisputeStatus.RESOLVED
                    d.resolution_type = Dispute.Resolution.REFUND_BUYER
                    d.resolution = 'Refunded automatically due to seller inactivity (48h timeout).'
                    d.resolved_at = now
                    d.save()
                    refund_count += 1
                    logger.info("Auto-refunded dispute %s due to seller inactivity.", d.id)
            except Exception as e:
                logger.error("Failed to auto-resolve dispute %s: %s", dispute.id, e)

    # ── 2. Warning Alerts (24h) ────────────────────────────────────────────────
    # Find disputes that reached 24h and haven't been warned yet
    # We use a simple marker in Dispute metadata if available, 
    # or just check if a notification exists for this seller+dispute.
    
    warning_eligible = Dispute.objects.filter(
        status=DisputeStatus.OPEN,
        created_at__lte=warning_cutoff,
        created_at__gt=resolution_cutoff # haven't hit refund yet
    ).select_related('transaction')

    warn_count = 0
    for dispute in warning_eligible:
        seller = dispute.transaction.seller_user
        if not seller: continue
        
        seller_evidence_exists = dispute.evidence.filter(submitted_by=seller).exists()
        if not seller_evidence_exists:
            # Check if we already sent an 'unresponsive_warning'
            already_warned = Notification.objects.filter(
                user=seller,
                data__dispute_id=str(dispute.id),
                type='dispute_warning'
            ).exists()
            
            if not already_warned:
                try:
                    from core.services.notifications import BaseNotificationService
                    notif_svc = BaseNotificationService()
                    msg = (
                        f"FINAL WARNING: You have 24 hours to respond to the dispute "
                        f"for transaction {dispute.transaction.reference} or the buyer "
                        f"will be automatically refunded."
                    )
                    notif_svc.create_db_notification(
                        user=seller,
                        type='dispute_warning',
                        title="Urgent: Dispute Action Required",
                        message=msg,
                        data={'dispute_id': str(dispute.id), 'transaction_reference': dispute.transaction.reference}
                    )
                    # Also try SMS
                    if hasattr(seller, 'profile') and seller.profile.phone_number:
                        notif_svc.sms.service.send_sms(seller.profile.phone_number, f"SmartDalali: {msg}")
                    
                    warn_count += 1
                except Exception as e:
                    logger.error("Failed to send dispute warning for %s: %s", dispute.id, e)

    return f"disputes_refunded={refund_count}, disputes_warned={warn_count}"
