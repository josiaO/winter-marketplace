"""
Prometheus metrics for the escrow engine (optional dependency).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest
except ImportError:  # pragma: no cover
    CONTENT_TYPE_LATEST = 'text/plain; version=0.0.4'

    def generate_latest() -> bytes:
        return b'# prometheus_client not installed\n'

    class _Noop:
        def labels(self, *a, **k):
            return self

        def inc(self, *a, **k):
            pass

        def observe(self, *a, **k):
            pass

        def time(self):
            return _NoopCtx()

    class _NoopCtx:
        def __enter__(self):
            return None

        def __exit__(self, *a):
            return False

    def Counter(*a, **k):
        return _Noop()

    def Histogram(*a, **k):
        return _Noop()


escrow_transactions_total = Counter(
    'escrow_transactions_total',
    'Escrow transaction state transitions observed',
    ['source'],
)

escrow_payments_success_total = Counter(
    'escrow_payments_success_total',
    'Successful payment confirmations',
)

escrow_payments_failed_total = Counter(
    'escrow_payments_failed_total',
    'Failed payment initiations or webhook verifications',
    ['stage'],
)

escrow_webhook_duplicate_total = Counter(
    'escrow_webhook_duplicate_total',
    'Webhooks skipped as idempotent duplicates',
)

escrow_payout_latency_seconds = Histogram(
    'escrow_payout_latency_seconds',
    'Time spent in process_payout (including gateway)',
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)
