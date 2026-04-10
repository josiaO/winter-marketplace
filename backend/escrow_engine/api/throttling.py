"""
Per API key rate limits for the Developer API (X-Api-Key).
"""
from __future__ import annotations

from django.core.cache import cache
from rest_framework.throttling import BaseThrottle


class EscrowDeveloperAPIKeyThrottle(BaseThrottle):
    """
    When ``APIKey.rate_limit_per_minute`` is set, enforce a fixed window per minute.
    Keys without a limit are not throttled by this class.
    """

    def allow_request(self, request, view) -> bool:
        key = getattr(request, 'auth', None)
        if key is None or not hasattr(key, 'pk'):
            return True
        limit = getattr(key, 'rate_limit_per_minute', None)
        if not limit:
            return True
        cache_key = f'escrow_dev_rl:{key.pk}'
        try:
            n = cache.incr(cache_key)
        except ValueError:
            cache.add(cache_key, 1, timeout=60)
            n = 1
        return n <= int(limit)
