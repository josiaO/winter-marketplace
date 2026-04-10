"""
Reconciliation: compare Order ↔ Transaction ↔ Payout, log mismatches, emit events.

Mutating auto-fix runs only when both ``RECONCILIATION_AUTO_FIX`` and
``RECONCILIATION_ALLOW_MUTATING_FIX`` are true. Otherwise detection is
logs + ``emit_event`` only.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Exists, OuterRef
from django.utils import timezone

from commerce.models import Order, StockReservation
from escrow_engine.models import Payout, Transaction
from escrow_engine.state_machine import TransactionStatus as TS

logger = logging.getLogger(__name__)


def _reconciliation_log_extra(**kwargs: Any) -> dict[str, Any]:
    try:
        from core.correlation import get_correlation_id

        cid = get_correlation_id()
        if cid:
            kwargs['correlation_id'] = cid
    except Exception:
        pass
    return kwargs


def _emit_anomaly(anomaly_code: str, **extra: Any) -> None:
    try:
        from core.events import emit_event

        emit_event(
            'RECONCILIATION_ANOMALY_DETECTED',
            {
                'anomaly_code': anomaly_code,
                **{k: v for k, v in extra.items() if v is not None},
            },
            source_module='commerce.reconciliation',
        )
    except Exception:
        logger.debug('reconciliation emit anomaly skipped', exc_info=True)


def _emit_auto_fix_applied(fix_code: str, **extra: Any) -> None:
    try:
        from core.events import emit_event

        emit_event(
            'RECONCILIATION_AUTO_FIX_APPLIED',
            {'fix_code': fix_code, **{k: v for k, v in extra.items() if v is not None}},
            source_module='commerce.reconciliation',
        )
    except Exception:
        logger.debug('reconciliation emit auto_fix skipped', exc_info=True)


def _issue(
    stats: dict[str, int],
    log_code: str,
    *,
    bus_code: str | None = None,
    **extra: Any,
) -> None:
    payload = _reconciliation_log_extra(
        reconciliation_code=log_code,
        **extra,
    )
    logger.warning('RECONCILIATION_MISMATCH', extra=payload)
    logger.error('RECONCILIATION_ERROR', extra=payload)
    _emit_anomaly(bus_code or log_code, **extra)
    stats['errors'] += 1


def _fix_applied(stats: dict[str, int], code: str, **extra: Any) -> None:
    logger.info(
        'RECONCILIATION_AUTO_FIX',
        extra=_reconciliation_log_extra(
            reconciliation_code=code,
            **extra,
        ),
    )
    _emit_auto_fix_applied(code, **extra)
    stats['fixes'] += 1


def _check_order_transaction(
    order: Order,
    stats: dict[str, int],
    *,
    auto_fix: bool,
) -> None:
    try:
        txn = order.engine_transaction
    except Exception:
        txn = None

    if txn is None:
        if order.status != 'pending' and (order.total_amount or 0) > 0:
            _issue(
                stats,
                'ORDER_MISSING_TRANSACTION',
                bus_code='ORDER_WITHOUT_TRANSACTION',
                order_id=order.pk,
                order_status=order.status,
            )
        return

    if txn.status == TS.RELEASED and order.status not in (
        'completed',
        'refunded',
        'cancelled',
    ):
        _issue(
            stats,
            'ORDER_NOT_TERMINAL_ESCROW_RELEASED',
            order_id=order.pk,
            order_status=order.status,
            transaction_id=str(txn.pk),
            transaction_status=txn.status,
        )

    if txn.status in (TS.HOLD, TS.PAID) and order.status == 'cancelled':
        _issue(
            stats,
            'ORDER_CANCELLED_ESCROW_ACTIVE',
            order_id=order.pk,
            transaction_id=str(txn.pk),
            transaction_status=txn.status,
        )

    if txn.status in (TS.HOLD, TS.PAID) and order.status == 'pending':
        bus = (
            'HOLD_BUT_ORDER_PENDING'
            if txn.status == TS.HOLD
            else 'PAID_BUT_ORDER_NOT_CONFIRMED'
        )
        _issue(
            stats,
            'HOLD_OR_PAID_BUT_ORDER_PENDING',
            bus_code=bus,
            order_id=order.pk,
            transaction_id=str(txn.pk),
            transaction_status=str(txn.status),
        )
        if auto_fix:
            from escrow_engine.integrations.commerce_sync import (
                sync_marketplace_order_on_escrow_hold,
            )

            try:
                sync_marketplace_order_on_escrow_hold(txn)
                _fix_applied(
                    stats,
                    'SYNC_ORDER_AFTER_ESCROW_PAID_OR_HOLD',
                    order_id=order.pk,
                    transaction_id=str(txn.pk),
                )
            except Exception as exc:
                _issue(
                    stats,
                    'AUTO_FIX_SYNC_ORDER_CONFIRM_FAILED',
                    order_id=order.pk,
                    transaction_id=str(txn.pk),
                    error=str(exc),
                )

    if txn.status == TS.REFUNDED and order.status not in ('cancelled', 'refunded'):
        _issue(
            stats,
            'ORDER_NOT_CANCELLED_ESCROW_REFUNDED',
            order_id=order.pk,
            order_status=order.status,
            transaction_id=str(txn.pk),
        )

    if (
        auto_fix
        and order.status == 'completed'
        and txn.status == TS.HOLD
    ):
        from commerce.services.escrow_bridge import safe_release_funds_for_order

        try:
            safe_release_funds_for_order(
                order,
                actor=None,
                actor_label='System: Reconciliation auto-fix',
                reason='RECONCILIATION_AUTO_FIX completed order + HOLD',
            )
            _fix_applied(
                stats,
                'RELEASED_STALE_HOLD',
                order_id=order.pk,
                transaction_id=str(txn.pk),
            )
        except Exception as exc:
            _issue(
                stats,
                'AUTO_FIX_RELEASE_FAILED',
                order_id=order.pk,
                transaction_id=str(txn.pk),
                error=str(exc),
            )


def _check_cancelled_order_reservations(
    stats: dict[str, int],
    *,
    auto_fix: bool,
    since,
    order_id: int | None = None,
) -> None:
    qs = StockReservation.objects.filter(
        order__status='cancelled',
        order__updated_at__gte=since,
        status__in=['reserved', 'confirmed'],
    ).select_related('order', 'listing')
    if order_id is not None:
        qs = qs.filter(order_id=order_id)
    for res in qs.iterator(chunk_size=200):
        _issue(
            stats,
            'RESERVATION_ACTIVE_ON_CANCELLED_ORDER',
            bus_code='STOCK_RESERVED_BUT_ORDER_CANCELLED',
            reservation_id=res.pk,
            order_id=res.order_id,
            listing_id=res.listing_id,
        )
        if auto_fix:
            try:
                res.release()
                _fix_applied(
                    stats,
                    'RESERVATION_RELEASED_CANCELLED_ORDER',
                    reservation_id=res.pk,
                    order_id=res.order_id,
                )
            except Exception as exc:
                _issue(
                    stats,
                    'AUTO_FIX_RESERVATION_RELEASE_FAILED',
                    reservation_id=res.pk,
                    error=str(exc),
                )


def _check_listing_stock_negative(stats: dict[str, int]) -> None:
    from listings.models import Listing

    for row in (
        Listing.objects.filter(track_inventory=True, stock_quantity__lt=0)
        .values('id', 'stock_quantity')
        .iterator(chunk_size=500)
    ):
        _issue(
            stats,
            'LISTING_NEGATIVE_STOCK',
            listing_id=row['id'],
            stock_quantity=row['stock_quantity'],
        )


def _check_expired_reservations_still_active(
    stats: dict[str, int],
    *,
    auto_fix: bool,
    order_id: int | None = None,
) -> None:
    now = timezone.now()
    qs = StockReservation.objects.filter(
        status__in=['reserved', 'confirmed'],
        expires_at__lte=now,
    )
    if order_id is not None:
        qs = qs.filter(order_id=order_id)
    for res in qs.select_related('listing', 'order').iterator(chunk_size=300):
        _issue(
            stats,
            'RESERVATION_EXPIRED_STILL_ACTIVE',
            reservation_id=res.pk,
            listing_id=res.listing_id,
            order_id=res.order_id,
        )
        if auto_fix:
            try:
                res.release()
                _fix_applied(
                    stats,
                    'RESERVATION_RELEASED_EXPIRED',
                    reservation_id=res.pk,
                    listing_id=res.listing_id,
                )
            except Exception as exc:
                _issue(
                    stats,
                    'AUTO_FIX_EXPIRED_RESERVATION_FAILED',
                    reservation_id=res.pk,
                    error=str(exc),
                )


def _check_missing_payouts(
    stats: dict[str, int],
    *,
    auto_fix: bool,
    since,
) -> None:
    has_payout = Exists(
        Payout.objects.filter(transaction_id=OuterRef('pk')),
    )
    qs = (
        Transaction.objects.filter(
            status=TS.RELEASED,
            updated_at__gte=since,
            seller_user__isnull=False,
        )
        .annotate(_has_payout=has_payout)
        .filter(_has_payout=False)
    )
    for txn in qs.select_related('seller_user').iterator(chunk_size=200):
        _issue(
            stats,
            'RELEASED_NO_PAYOUT_RECORD',
            transaction_id=str(txn.pk),
            reference=txn.reference,
            seller_user_id=txn.seller_user_id,
        )
        if auto_fix:
            try:
                from escrow_engine.services.payout import create_payout

                payout = create_payout(txn)
                if payout is not None:
                    _fix_applied(
                        stats,
                        'PAYOUT_RECORD_CREATED',
                        transaction_id=str(txn.pk),
                        reference=txn.reference,
                    )
            except Exception as exc:
                _issue(
                    stats,
                    'AUTO_FIX_CREATE_PAYOUT_FAILED',
                    transaction_id=str(txn.pk),
                    error=str(exc),
                )


def _check_transaction_without_order(
    stats: dict[str, int],
    *,
    since,
) -> None:
    """Transaction.linked_order_id points to a missing Order row."""
    for txn in (
        Transaction.objects.filter(
            linked_order_id__isnull=False,
            updated_at__gte=since,
        )
        .iterator(chunk_size=300)
    ):
        if not Order.objects.filter(pk=txn.linked_order_id).exists():
            _issue(
                stats,
                'TRANSACTION_LINKED_ORDER_MISSING',
                bus_code='TRANSACTION_WITHOUT_ORDER',
                transaction_id=str(txn.pk),
                linked_order_id=txn.linked_order_id,
            )


def run_reconciliation_scan(
    *,
    lookback_days: int | None = None,
    auto_fix: bool | None = None,
    order_id: int | None = None,
) -> dict[str, int]:
    """
    Scan recent marketplace data for inconsistencies.

    ``auto_fix`` defaults to settings.RECONCILIATION_AUTO_FIX (False).
    When ``order_id`` is set, only checks involving that order (plus global listing stock).
    """
    days = lookback_days if lookback_days is not None else getattr(
        settings, 'RECONCILIATION_LOOKBACK_DAYS', 30
    )
    fix = (
        auto_fix
        if auto_fix is not None
        else getattr(settings, 'RECONCILIATION_AUTO_FIX', False)
    )
    allow_mutating = getattr(settings, 'RECONCILIATION_ALLOW_MUTATING_FIX', False)
    effective_fix = bool(fix and allow_mutating)
    since = timezone.now() - timedelta(days=days)
    stats: dict[str, int] = {
        'errors': 0,
        'fixes': 0,
        'orders_scanned': 0,
        'scoped_order_id': order_id or 0,
    }

    try:
        if order_id is not None:
            order = (
                Order.objects.filter(pk=order_id)
                .select_related('engine_transaction')
                .first()
            )
            if order:
                stats['orders_scanned'] += 1
                _check_order_transaction(order, stats, auto_fix=effective_fix)
            _check_cancelled_order_reservations(
                stats, auto_fix=effective_fix, since=since, order_id=order_id
            )
            _check_expired_reservations_still_active(
                stats, auto_fix=effective_fix, order_id=order_id
            )
            _check_listing_stock_negative(stats)
        else:
            order_qs = Order.objects.filter(created_at__gte=since).select_related(
                'engine_transaction',
            )
            for order in order_qs.iterator(chunk_size=300):
                stats['orders_scanned'] += 1
                _check_order_transaction(order, stats, auto_fix=effective_fix)

            _check_cancelled_order_reservations(stats, auto_fix=effective_fix, since=since)
            _check_listing_stock_negative(stats)
            _check_expired_reservations_still_active(stats, auto_fix=effective_fix)
            _check_missing_payouts(stats, auto_fix=effective_fix, since=since)
            _check_transaction_without_order(stats, since=since)

        logger.info(
            'RECONCILIATION_SCAN_COMPLETE',
            extra=_reconciliation_log_extra(
                reconciliation_code='SCAN_COMPLETE',
                lookback_days=days,
                auto_fix_requested=fix,
                auto_fix_effective=effective_fix,
                order_id=order_id,
                **stats,
            ),
        )
        return stats
    except Exception as exc:
        logger.exception(
            'RECONCILIATION_CRITICAL_ERROR: %s',
            exc,
            extra=_reconciliation_log_extra(),
        )
        try:
            from core.events import emit_event

            emit_event(
                'RECONCILIATION_CRITICAL_ERROR',
                {'error': str(exc)[:4000]},
                source_module='commerce.reconciliation',
            )
        except Exception:
            logger.debug('emit RECONCILIATION_CRITICAL_ERROR skipped', exc_info=True)
        raise

