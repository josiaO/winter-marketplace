"""
Structured INFO logs for escrow events (parseable by log aggregators / metrics pipelines).

No external services required; format is stable: escrow_metric key=value ...
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger('escrow_engine.metrics')


def log_escrow_metric(event: str, **fields: Any) -> None:
    """Emit a single-line metric-oriented log entry."""
    safe = []
    for k, v in sorted(fields.items()):
        if v is None:
            continue
        s = str(v).replace('\n', ' ').replace('\r', ' ')[:500]
        safe.append(f'{k}={s}')
    tail = ' '.join(safe)
    logger.info('escrow_metric event=%s %s', event, tail)


def log_escrow_failure(
    event: str,
    message: str,
    *,
    severity: str = 'critical',
    **fields: Any,
) -> None:
    """
    Structured failure line for SLO / alerting (Datadog, CloudWatch, ELK).
    event should stay stable, e.g. escrow.failure
    """
    safe = [f'severity={severity}', f'message={message.replace(chr(10), " ")[:500]}']
    for k, v in sorted(fields.items()):
        if v is None:
            continue
        s = str(v).replace('\n', ' ').replace('\r', ' ')[:500]
        safe.append(f'{k}={s}')
    tail = ' '.join(safe)
    logger.error('escrow_failure event=%s %s', event, tail)
