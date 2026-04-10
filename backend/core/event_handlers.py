"""
Async event handler registry (Celery worker).

Handlers must be side effects only: notifications, analytics, logging, scoped scans.
Do not mutate order/escrow state here — that stays in synchronous services.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _maybe_run_order_reconciliation(payload: dict[str, Any]) -> None:
    oid = payload.get('order_id')
    if oid is None:
        return
    try:
        from commerce.services.reconciliation import run_reconciliation_scan

        run_reconciliation_scan(order_id=int(oid), lookback_days=30, auto_fix=False)
    except Exception:
        logger.exception(
            'Scoped reconciliation after event failed (order_id=%s)',
            oid,
        )


def handle_event(event_name: str, payload: dict) -> None:
    data = payload or {}
    if event_name == 'ORDER_CREATED':
        handle_order_created(data)
    elif event_name == 'ORDER_CONFIRMED':
        handle_order_confirmed(data)
    elif event_name == 'ORDER_SHIPPED':
        handle_order_shipped(data)
    elif event_name == 'ORDER_DELIVERED':
        handle_order_delivered(data)
    elif event_name == 'ORDER_COMPLETED':
        handle_order_completed(data)
    elif event_name == 'ORDER_CANCELLED':
        handle_order_cancelled(data)
    elif event_name == 'PAYMENT_CONFIRMED':
        handle_payment_confirmed(data)
    elif event_name == 'ESCROW_FUNDS_RELEASED':
        handle_escrow_funds_released(data)
    elif event_name == 'ESCROW_REFUND_APPLIED':
        handle_escrow_refund_applied(data)
    elif event_name == 'ORDER_DISPUTE_OPENED':
        handle_order_dispute_opened(data)
    elif event_name == 'ORDER_DISPUTE_RESOLVED':
        handle_order_dispute_resolved(data)
    elif event_name == 'RECONCILIATION_ANOMALY_DETECTED':
        handle_reconciliation_anomaly_detected(data)
    elif event_name == 'RECONCILIATION_AUTO_FIX_APPLIED':
        handle_reconciliation_auto_fix_applied(data)
    elif event_name == 'RECONCILIATION_CRITICAL_ERROR':
        handle_reconciliation_critical_error(data)
    elif event_name == 'PAYMENT_VERIFICATION_FAILED':
        handle_payment_verification_failed(data)
    elif event_name == 'PAYOUT_PROCESSING_FAILED':
        handle_payout_processing_failed(data)
    elif event_name == 'EVENT_HANDLER_FAILED':
        handle_event_handler_failed(data)
    else:
        logger.debug('No async handler for event %s', event_name)


def handle_order_created(payload: dict[str, Any]) -> None:
    _ = payload.get('order_id')


def handle_order_confirmed(payload: dict[str, Any]) -> None:
    _ = payload.get('order_id')


def handle_order_shipped(payload: dict[str, Any]) -> None:
    _ = payload.get('order_id')


def handle_order_delivered(payload: dict[str, Any]) -> None:
    _ = payload.get('order_id')


def handle_order_completed(payload: dict[str, Any]) -> None:
    logger.debug(
        'ORDER_COMPLETED side effects placeholder order_id=%s',
        payload.get('order_id'),
    )
    _maybe_run_order_reconciliation(payload)


def handle_order_cancelled(payload: dict[str, Any]) -> None:
    _ = payload.get('order_id')


def handle_payment_confirmed(payload: dict[str, Any]) -> None:
    _maybe_run_order_reconciliation(payload)


def handle_escrow_funds_released(payload: dict[str, Any]) -> None:
    _maybe_run_order_reconciliation(payload)


def handle_escrow_refund_applied(payload: dict[str, Any]) -> None:
    _ = payload.get('order_id')


def handle_order_dispute_opened(payload: dict[str, Any]) -> None:
    _ = payload.get('order_id')


def handle_order_dispute_resolved(payload: dict[str, Any]) -> None:
    _ = payload.get('order_id')


def handle_reconciliation_anomaly_detected(payload: dict[str, Any]) -> None:
    logger.info(
        '[RECONCILIATION_ANOMALY_EVENT] %s',
        payload.get('anomaly_code'),
        extra={'payload': payload},
    )


def handle_reconciliation_auto_fix_applied(payload: dict[str, Any]) -> None:
    logger.info(
        '[RECONCILIATION_AUTO_FIX_EVENT] %s',
        payload.get('fix_code'),
        extra={'payload': payload},
    )


def handle_reconciliation_critical_error(payload: dict[str, Any]) -> None:
    logger.error(
        '[RECONCILIATION_CRITICAL_ERROR_EVENT] %s',
        payload.get('error', '')[:500],
        extra={'payload': payload},
    )


def handle_payment_verification_failed(payload: dict[str, Any]) -> None:
    logger.warning(
        '[PAYMENT_VERIFICATION_FAILED_EVENT] ref=%s',
        payload.get('transaction_reference'),
        extra={'payload': payload},
    )


def handle_payout_processing_failed(payload: dict[str, Any]) -> None:
    logger.error(
        '[PAYOUT_PROCESSING_FAILED_EVENT] payout=%s order=%s',
        payload.get('payout_id'),
        payload.get('order_id'),
        extra={'payload': payload},
    )


def handle_event_handler_failed(payload: dict[str, Any]) -> None:
    logger.error(
        '[EVENT_HANDLER_FAILED_EVENT] original=%s',
        payload.get('failed_event_name'),
        extra={'payload': payload},
    )
