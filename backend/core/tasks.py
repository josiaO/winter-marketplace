"""
Celery tasks for the core app (event dispatch, outbox publisher).

Domain rules and money flows stay synchronous; tasks here run side effects only.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


def _finalize_outbox_delivery(outbox_pk: int, event_name: str, payload: dict) -> None:
    """After DB commit: hand off to Celery, then mark outbox SENT (or retry as PENDING)."""
    from core.models import OutboxEvent

    max_retries = int(getattr(settings, 'OUTBOX_PUBLISH_MAX_RETRIES', 10))
    try:
        dispatch_event_task.delay(event_name, payload)
    except Exception as exc:
        row = OutboxEvent.objects.filter(pk=outbox_pk).first()
        if row:
            row.retry_count += 1
            row.last_error = str(exc)[:8000]
            if row.retry_count >= max_retries:
                row.status = OutboxEvent.Status.FAILED
            else:
                row.status = OutboxEvent.Status.PENDING
            row.save(
                update_fields=['retry_count', 'last_error', 'status', 'updated_at']
            )
        logger.warning(
            'outbox finalize enqueue failed id=%s: %s',
            outbox_pk,
            exc,
            exc_info=True,
        )
        return
    OutboxEvent.objects.filter(pk=outbox_pk).update(
        status=OutboxEvent.Status.SENT,
        last_error='',
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def dispatch_event_task(self, event_name: str, payload: dict | None) -> None:
    from core.correlation import reset_correlation_id, set_correlation_id
    from core.event_handlers import handle_event

    raw = dict(payload or {})
    meta = raw.pop('_event_meta', {}) or {}
    cid = meta.get('correlation_id')
    token = set_correlation_id(str(cid)) if cid else None
    try:
        logger.info(
            '[EVENT_DISPATCHED] %s',
            event_name,
            extra={
                'event_name': event_name,
                'correlation_id': meta.get('correlation_id'),
                'source_module': meta.get('source_module'),
                'timestamp': meta.get('timestamp'),
            },
        )
        handle_event(event_name, raw)
    except Exception as exc:
        logger.exception(
            '[EVENT_FAILED] handler error for %s: %s',
            event_name,
            exc,
            extra={
                'event_name': event_name,
                'correlation_id': meta.get('correlation_id'),
                'source_module': meta.get('source_module'),
            },
        )
        try:
            from core.events import emit_event

            emit_event(
                'EVENT_HANDLER_FAILED',
                {
                    'failed_event_name': event_name,
                    'error': str(exc)[:2000],
                    'task_id': getattr(self.request, 'id', None),
                },
                source_module='core.tasks.dispatch_event_task',
                correlation_id=meta.get('correlation_id'),
            )
        except Exception:
            logger.debug('emit EVENT_HANDLER_FAILED skipped', exc_info=True)
        raise
    finally:
        if token is not None:
            reset_correlation_id(token)


@shared_task(bind=True)
def publish_outbox_events(self, batch_size: int | None = None) -> dict[str, int]:
    """
    Publish pending OutboxEvent rows to Celery (at-least-once handoff to broker).
    Enqueue runs in transaction.on_commit so workers never see events before commit.
    """
    from core.models import OutboxEvent

    limit = batch_size or int(getattr(settings, 'OUTBOX_PUBLISH_BATCH_SIZE', 100))
    stats = {'scheduled': 0, 'skipped': 0}

    for _ in range(limit):
        try:
            with transaction.atomic():
                row = (
                    OutboxEvent.objects.select_for_update(skip_locked=True)
                    .filter(status=OutboxEvent.Status.PENDING)
                    .order_by('created_at')
                    .first()
                )
                if row is None:
                    break
                oid = row.pk
                ename = row.event_name
                pld = dict(row.payload or {})
                transaction.on_commit(
                    lambda pk=oid, name=ename, data=pld: _finalize_outbox_delivery(
                        pk, name, data
                    )
                )
                stats['scheduled'] += 1
        except Exception:
            logger.exception('publish_outbox_events iteration failed')
            stats['skipped'] += 1

    return stats


@shared_task(name='core.tasks.publish_outbox_events_periodic')
def publish_outbox_events_periodic() -> dict[str, int]:
    return publish_outbox_events()
