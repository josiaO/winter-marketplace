"""
escrow_engine.providers.registry
---------------------------------
Provider registry — resolves payment_method strings to provider instances.
Extend this dict as new gateways are added.
"""
from .selcom import SelcomProvider

_SELCOM_CHANNELS = {
    # ── Mobile Money (all TZ operators) ────────────────────────────────────
    'selcom',
    'mpesa',
    'tigo_pesa',
    'airtel_money',
    'halopesa',
    'ezypesa',
    'azampesa',
    # ── Banks (40+ via Selcom bridge) ───────────────────────────────────────
    'bank',
    # ── Cards ───────────────────────────────────────────────────────────────
    'card',
    'card_visa',
    'card_mastercard',
    'card_unionpay',
    # ── Selcom Pay (Till / TanQR / Masterpass QR) ───────────────────────────
    'till',
    'tanqr',
    'mobile_money',   # generic fallback key
}

# All of the above route through SelcomProvider (it handles channel routing internally)
_PROVIDER_MAP = {channel: SelcomProvider for channel in _SELCOM_CHANNELS}

# Future gateways — uncomment when provider classes are implemented:
# _PROVIDER_MAP['stripe'] = StripeProvider
# _PROVIDER_MAP['flutterwave'] = FlutterwaveProvider

_DEFAULT_PROVIDER = SelcomProvider

# Methods that skip hosted checkout (cash, manual reconciliation, etc.)
_OFFLINE_CHECKOUT_METHODS = frozenset({
    'manual', 'cash_on_delivery', 'cod', 'pay_at_pickup', 'invoice', 'offline',
})


def should_open_payment_gateway(payment_method: str | None) -> bool:
    """
    True when checkout should call initiate_payment and return a gateway URL.
    False for offline / manual flows handled outside the aggregator.
    """
    if payment_method is None or payment_method == '':
        return True
    key = payment_method.lower().replace('-', '_')
    return key not in _OFFLINE_CHECKOUT_METHODS


def get_provider(payment_method: str = None, transaction=None):
    """
    Return an instantiated provider for the given method or transaction.
    Selection logic:
      1. transaction.preferred_provider (if set)
      2. Stripe if currency is USD
      3. payment_method string if provided
      4. Default to Selcom
    """
    provider_key = None
    
    if transaction:
        if getattr(transaction, 'preferred_provider', None):
            provider_key = transaction.preferred_provider
        elif getattr(transaction, 'currency', 'TZS') == 'USD':
            provider_key = 'stripe'
    
    if not provider_key:
        provider_key = (payment_method or 'selcom').lower()

    cls = _PROVIDER_MAP.get(provider_key, _DEFAULT_PROVIDER)
    return cls()
