"""Scoped throttles for abuse-prone commerce endpoints."""
from rest_framework.throttling import UserRateThrottle


class CommerceCheckoutThrottle(UserRateThrottle):
    scope = 'commerce_checkout'


class CommercePaymentInitiateThrottle(UserRateThrottle):
    scope = 'commerce_payment_initiate'


class CommercePaymentReturnThrottle(UserRateThrottle):
    scope = 'commerce_payment_return'


class CommerceDisputeThrottle(UserRateThrottle):
    scope = 'commerce_dispute'
