"""
Gate for commerce.Order.status writes (single lifecycle path).

Source of Truth: only OrderLifecycleManager, escrow-driven sync helpers, and
explicit bypass contexts may change Order.status. Everyone else must go through
lifecycle APIs.

``order_status_write_context(order)`` sets the instance flag expected by Order.save()
(and keeps a contextvar for nested calls that lack the instance reference).
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

_order_status_mutation_allowed: ContextVar[bool] = ContextVar(
    '_order_status_mutation_allowed', default=False
)


@contextmanager
def allow_order_status_mutation():
    """Legacy global allow (prefer order_status_write_context)."""
    token = _order_status_mutation_allowed.set(True)
    try:
        yield
    finally:
        _order_status_mutation_allowed.reset(token)


@contextmanager
def order_status_write_context(order):
    """Authorized channel for mutating this order's status (lifecycle / escrow sync)."""
    if order is None:
        raise ValueError('order_status_write_context requires an Order instance.')
    token = _order_status_mutation_allowed.set(True)
    order._allow_status_transition = True
    try:
        yield
    finally:
        _order_status_mutation_allowed.reset(token)
        if hasattr(order, '_allow_status_transition'):
            delattr(order, '_allow_status_transition')


def order_status_mutation_is_allowed() -> bool:
    return _order_status_mutation_allowed.get()
