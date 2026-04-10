from rest_framework.throttling import AnonRateThrottle


class AuthLoginThrottle(AnonRateThrottle):
    """
    Throttle for login attempts (SimpleJWT token obtain).

    Uses IP-based keys (AnonRateThrottle). Rate configured via
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['auth_login'].
    """

    scope = "auth_login"


class AuthRefreshThrottle(AnonRateThrottle):
    """
    Throttle for refresh attempts (SimpleJWT token refresh).

    Uses IP-based keys (AnonRateThrottle). Rate configured via
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['auth_refresh'].
    """

    scope = "auth_refresh"

