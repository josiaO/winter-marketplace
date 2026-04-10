"""Small helpers for Django REST framework viewsets."""

from __future__ import annotations

from typing import Optional


def viewset_mapped_action(view) -> Optional[str]:
    """
    Resolve the ViewSet action for the current request without using ``view.action``.

    ``get_authenticators()`` runs from ``APIView.initialize_request()`` before
    ``ViewSetMixin`` assigns ``view.action``, so action-based branching there
    raises AttributeError. The router-bound ``action_map`` is available on the
    instance together with the Django ``HttpRequest`` set in ``as_view``.
    """
    request = getattr(view, "request", None)
    if request is None:
        return None
    method = request.method.lower()
    if method == "options":
        return "metadata"
    action_map = getattr(view, "action_map", None) or {}
    return action_map.get(method)
