"""
Rate limits for public escrow payment-link flows (OTP / pay).

Rates are defined in REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] (see project settings).
Uses IP + payment-link token so one abusive client cannot exhaust quota for all links.
"""
from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class EscrowPaymentLinkScopedThrottle(SimpleRateThrottle):
    """
    Per (payment link token, client IP) bucket for anonymous payment-link endpoints.
    """

    scope = 'escrow_payment_link'

    def get_cache_key(self, request, view):
        token = getattr(view, 'kwargs', {}).get('token')
        if token is None:
            return None
        ident = self.get_ident(request)
        # Scope cache key by token so limits apply per link, not globally per IP.
        return self.cache_format % {
            'scope': f'{self.scope}_{token}',
            'ident': ident,
        }
