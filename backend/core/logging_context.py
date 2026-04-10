"""Structured log extras (correlation_id + domain ids)."""
from __future__ import annotations

from typing import Any


def log_extra(**kwargs: Any) -> dict[str, Any]:
    """Merge correlation_id from request context when available."""
    extra = {k: v for k, v in kwargs.items() if v is not None}
    try:
        from core.correlation import get_correlation_id

        cid = get_correlation_id()
        if cid:
            extra.setdefault('correlation_id', cid)
    except Exception:
        pass
    return extra
