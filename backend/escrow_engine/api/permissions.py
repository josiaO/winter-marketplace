"""
Scope checks for Developer API (request.auth is APIKey).
"""
from rest_framework.permissions import BasePermission

from escrow_engine.models import APIKey


class HasEscrowAPIKey(BasePermission):
    """Request must be authenticated with a valid APIKey on request.auth."""

    def has_permission(self, request, view):
        return isinstance(getattr(request, 'auth', None), APIKey)


class EscrowAPIKeyScopes(BasePermission):
    """
    Map DRF action → required scope.
    """

    def has_permission(self, request, view):
        key = getattr(request, 'auth', None)
        if not isinstance(key, APIKey):
            return False

        action = getattr(view, 'action', None)
        if action is None:
            return False

        required = self._required_scope(view, action)
        if required is None:
            return True
        return key.has_scope(required)

    def _required_scope(self, view, action: str):
        basename = getattr(view, 'basename', '') or ''

        if basename == 'dev-transaction':
            if action in ('list', 'retrieve'):
                return 'read'
            if action == 'create':
                return 'write'
            if action == 'pay':
                return 'pay'
            if action == 'release':
                return 'release'
            if action == 'refund':
                return 'refund'
            return None

        if basename == 'dev-dispute':
            if action in ('list', 'retrieve'):
                return 'read'
            if action == 'create':
                return 'write'
            return None

        return None
