"""Attach a correlation ID to each HTTP request for distributed tracing."""
from __future__ import annotations

import uuid

from core.correlation import reset_correlation_id, set_correlation_id


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        header_cid = (request.META.get('HTTP_X_CORRELATION_ID') or '').strip()
        cid = header_cid or str(uuid.uuid4())
        request.correlation_id = cid
        token = set_correlation_id(cid)
        try:
            response = self.get_response(request)
            if response is not None:
                try:
                    response['X-Correlation-ID'] = cid
                except (TypeError, AttributeError):
                    pass
            return response
        finally:
            reset_correlation_id(token)
