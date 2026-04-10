"""
Redis distributed locks for multi-instance escrow safety.
Falls back to django.core.cache.add when Redis is unavailable (best-effort).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def _redis_client():
    from django_redis import get_redis_connection

    return get_redis_connection('default')


@contextmanager
def escrow_distributed_lock(
    lock_key: str,
    *,
    ttl_sec: int = 180,
    blocking_timeout: float = 10.0,
) -> Iterator[bool]:
    """
    Yield True if the lock was acquired, False otherwise.
    Always releases when acquired.
    """
    try:
        client = _redis_client()
        lock = client.lock(
            lock_key,
            timeout=ttl_sec,
            blocking_timeout=blocking_timeout,
        )
        acquired = lock.acquire(blocking=True)
        try:
            yield acquired
        finally:
            if acquired:
                try:
                    lock.release()
                except Exception:
                    logger.debug('Lock release noop for %s', lock_key, exc_info=True)
    except Exception as exc:
        logger.warning(
            'Redis lock unavailable for %s (%s); falling back to cache lock',
            lock_key,
            exc,
        )
        acquired = cache.add(lock_key, 1, timeout=ttl_sec)
        try:
            yield acquired
        finally:
            if acquired:
                cache.delete(lock_key)
