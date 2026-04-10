"""
Bounded retries with exponential backoff for outbound gateway HTTP calls.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


def call_with_gateway_retry(
    fn: Callable[[], T],
    *,
    retries: int = 3,
    backoff_base: float = 0.5,
    operation: str = 'gateway',
) -> T:
    """
    Run ``fn`` up to ``retries`` times with exponential backoff + small jitter.
    Re-raises the last exception if all attempts fail.
    """
    last_exc: BaseException | None = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            logger.warning(
                '%s attempt %s/%s failed: %s',
                operation,
                attempt + 1,
                retries,
                exc,
            )
            if attempt >= retries - 1:
                break
            sleep_s = backoff_base * (2**attempt) + random.uniform(0, 0.15)
            time.sleep(sleep_s)
    assert last_exc is not None
    raise last_exc
