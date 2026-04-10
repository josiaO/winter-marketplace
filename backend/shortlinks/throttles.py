from rest_framework.throttling import AnonRateThrottle


class ShortLinkCreateThrottle(AnonRateThrottle):
    """
    Throttle for public shortlink creation.

    Uses IP-based keys (AnonRateThrottle). Rate configured via
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['shortlinks_create'].
    """

    scope = "shortlinks_create"

