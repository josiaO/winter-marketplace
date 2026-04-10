import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health_check(request):
    """
    Liveness / monitoring: DB required; cache and Celery failures yield degraded (still 200)
    so platforms do not recycle the web process when workers are briefly unavailable.
    """
    payload = {
        'status': 'healthy',
        'timestamp': time.time(),
        'database': 'unknown',
        'cache': 'unknown',
        'celery': 'unknown',
    }

    try:
        connection.ensure_connection()
        payload['database'] = 'connected'
    except Exception as exc:
        logger.warning('Health DB check failed: %s', exc)
        payload['database'] = f'error: {str(exc)[:100]}'
        payload['status'] = 'unhealthy'

    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') == 'ok':
            payload['cache'] = 'connected'
        else:
            payload['cache'] = 'stale'
            if payload['status'] == 'healthy':
                payload['status'] = 'degraded'
    except Exception as exc:
        payload['cache'] = f'error: {str(exc)[:100]}'
        if payload['status'] == 'healthy':
            payload['status'] = 'degraded'

    if getattr(settings, 'ESCROW_WEBHOOK_ASYNC', False):
        try:
            from backend.celery import app as celery_app

            inspector = celery_app.control.inspect(timeout=1.0)
            pong = inspector.ping() if inspector else None
            if pong:
                payload['celery'] = 'connected'
            else:
                payload['celery'] = 'no_workers'
                if payload['status'] == 'healthy':
                    payload['status'] = 'degraded'
        except Exception as exc:
            payload['celery'] = f'error: {str(exc)[:100]}'
            if payload['status'] == 'healthy':
                payload['status'] = 'degraded'
    else:
        payload['celery'] = 'skipped_sync_webhooks'

    code = 503 if payload['status'] == 'unhealthy' else 200
    return JsonResponse(payload, status=code)


def readiness_check(request):
    """
    Readiness for load balancers: require database. Cache failures return 200 with status degraded
    so brief Redis blips do not drain the entire service (sessions use cache with IGNORE_EXCEPTIONS).
    """
    status = {
        'database': False,
        'cache': False,
        'status': 'unhealthy',
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            if cursor.fetchone()[0] == 1:
                status['database'] = True
    except Exception as exc:
        status['database_error'] = str(exc)

    try:
        cache.set('health_check_key', 'value', timeout=5)
        status['cache'] = cache.get('health_check_key') == 'value'
    except Exception as exc:
        status['cache_error'] = str(exc)

    if not status['database']:
        return JsonResponse(status, status=503)

    _cache_backend = getattr(settings, 'CACHES', {}).get('default', {}).get('BACKEND', '')
    if 'LocMemCache' in _cache_backend:
        status['cache'] = True
        status['cache_note'] = 'locmem_assumed_ok'

    status['status'] = 'ready' if status['cache'] else 'degraded'
    return JsonResponse(status, status=200)
