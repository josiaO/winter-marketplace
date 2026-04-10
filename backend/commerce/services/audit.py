"""Append-only order audit logging for compliance and incident response."""
from __future__ import annotations

from commerce.models import Order, OrderAuditLog


def write_order_audit(
    order: Order | None,
    action: str,
    *,
    actor=None,
    from_status: str = '',
    to_status: str = '',
    metadata=None,
) -> None:
    if order is None or not getattr(order, 'pk', None):
        return
    meta = dict(metadata or {})
    cid = ''
    try:
        from core.correlation import get_correlation_id

        cid = get_correlation_id() or ''
        if cid and 'correlation_id' not in meta:
            meta['correlation_id'] = cid
    except Exception:
        pass
    OrderAuditLog.objects.create(
        order=order,
        action=action,
        from_status=from_status or '',
        to_status=to_status or '',
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        metadata=meta,
        correlation_id=(cid or '')[:64],
    )
