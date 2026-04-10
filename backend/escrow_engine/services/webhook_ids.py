"""
Stable provider-specific webhook event identifiers for idempotency.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def extract_webhook_event_id(provider: str, gateway_data: dict[str, Any]) -> str:
    provider_norm = (provider or 'unknown').lower()
    if provider_norm == 'selcom':
        return _selcom_event_id(gateway_data)
    raw = json.dumps(gateway_data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:64]


def _selcom_event_id(data: dict[str, Any]) -> str:
    for key in ('event_id', 'uuid', 'webhook_id', 'id'):
        v = data.get(key)
        if v is not None and str(v).strip():
            return str(v)[:255]
    ref = str(data.get('reference') or data.get('transid') or '')
    canonical = json.dumps(data, sort_keys=True, default=str)
    digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:64]
    if ref:
        composite = f'{ref}:{digest}'
        return composite[:255]
    return digest
