"""
Domain event emission (observability + reliable async dispatch).

Inside an open DB transaction, events are persisted to OutboxEvent and published
by ``publish_outbox_events`` after commit. Outside a transaction, events enqueue
immediately via Celery.

Cross-app business rules remain synchronous; this module does not replace direct
calls to escrow_engine / commerce lifecycle services.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Mapping

from django.db import connection
from django.utils import timezone

from core.correlation import get_correlation_id

logger = logging.getLogger(__name__)


def _json_safe_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    """Ensure Celery JSON serializer can encode the payload."""
    try:
        return json.loads(json.dumps(dict(data), default=str))
    except (TypeError, ValueError):
        return {str(k): str(v) for k, v in dict(data).items()}


def _build_envelope(
    data: dict[str, Any],
    *,
    source_module: str,
    correlation_id: str | None,
) -> dict[str, Any]:
    cid = correlation_id if correlation_id is not None else get_correlation_id()
    meta = {
        'correlation_id': cid,
        'timestamp': timezone.now().isoformat(),
        'source_module': source_module,
    }
    return {**data, '_event_meta': meta}


def emit_event(
    event_name: str,
    payload: Mapping[str, Any] | None = None,
    *,
    source_module: str = 'core',
    correlation_id: str | None = None,
) -> None:
    """
    Emit a domain event: structured log + outbox (in transaction) or Celery enqueue.

    Must never raise to callers (broker down, serialization, DB errors).
    """
    base = _json_safe_payload(payload or {})
    envelope = _build_envelope(
        base,
        source_module=source_module,
        correlation_id=correlation_id,
    )
    meta = envelope.get('_event_meta') or {}

    try:
        log_extra = {
            'event_name': event_name,
            'correlation_id': meta.get('correlation_id'),
            'source_module': meta.get('source_module'),
            'timestamp': meta.get('timestamp'),
            **{k: str(v) for k, v in base.items()},
        }
        logger.info('[EVENT_EMITTED] %s', event_name, extra=log_extra)
    except Exception:
        logger.debug('emit_event log skipped for %s', event_name, exc_info=True)

    try:
        if connection.in_atomic_block:
            from core.models import OutboxEvent

            OutboxEvent.objects.create(
                event_name=event_name,
                payload=envelope,
                status=OutboxEvent.Status.PENDING,
            )
            return

        from core.tasks import dispatch_event_task

        dispatch_event_task.delay(event_name, envelope)
    except Exception:
        logger.warning(
            '[EVENT_FAILED] emit_event could not persist or enqueue for %s',
            event_name,
            exc_info=True,
            extra={
                'event_name': event_name,
                'correlation_id': meta.get('correlation_id'),
                'source_module': meta.get('source_module'),
            },
        )
