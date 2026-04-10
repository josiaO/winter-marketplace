"""
Celery entry points for reconciliation (kept separate from commerce.tasks for clarity).
Loaded from commerce.tasks so autodiscover picks up the periodic job.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name='commerce.tasks.reconcile_orders_escrow_periodic')
def reconciliation_scan_periodic():
    """
    Periodic reconciliation: order↔txn, stock, payout records (optional auto-fix).
    """
    from commerce.services.reconciliation import run_reconciliation_scan

    days = getattr(settings, 'RECONCILIATION_LOOKBACK_DAYS', 30)
    auto = getattr(settings, 'RECONCILIATION_AUTO_FIX', False)
    try:
        stats = run_reconciliation_scan(lookback_days=days, auto_fix=auto)
        return stats
    except Exception as exc:
        logger.exception('reconciliation_scan_periodic failed: %s', exc)
        raise


@shared_task(name='commerce.tasks.reconciliation_healing_periodic')
def reconciliation_healing_periodic():
    """
    Frequent scan with auto_fix=True for deterministic, safe repairs only
    (see commerce.services.reconciliation).
    """
    from commerce.services.reconciliation import run_reconciliation_scan

    days = getattr(settings, 'RECONCILIATION_LOOKBACK_DAYS', 30)
    try:
        return run_reconciliation_scan(lookback_days=days, auto_fix=True)
    except Exception as exc:
        logger.exception('reconciliation_healing_periodic failed: %s', exc)
        raise
