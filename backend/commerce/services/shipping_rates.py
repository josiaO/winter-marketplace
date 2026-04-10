"""
Server-side shipping fees for checkout (commerce domain).

Clients must not choose arbitrary shipping_cost; checkout resolves the fee from
`shipping_method` using `settings.COMMERCE_SHIPPING_RATES`.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings


def _rates() -> dict[str, Decimal]:
    raw = getattr(settings, 'COMMERCE_SHIPPING_RATES', None)
    if not raw:
        return {
            'standard': Decimal('5000.00'),
            'express': Decimal('15000.00'),
            'pickup': Decimal('0.00'),
        }
    out: dict[str, Decimal] = {}
    for k, v in raw.items():
        key = str(k).strip().lower()
        out[key] = v if isinstance(v, Decimal) else Decimal(str(v))
    return out


def shipping_cost_for_method(method: str | None) -> Decimal:
    """Return the platform shipping fee for a checkout method key."""
    key = (method or 'standard').strip().lower()
    rates = _rates()
    if key not in rates:
        allowed = ', '.join(sorted(rates))
        raise ValueError(f'Unknown shipping_method "{method}". Allowed: {allowed}')
    return rates[key]


def list_shipping_options() -> list[dict]:
    """
    Public catalog for UI: method key, human label, description, fee, currency.
    """
    rates = _rates()
    meta = {
        'standard': {
            'label': 'Standard delivery',
            'description': 'Typical dispatch within a few business days',
        },
        'express': {
            'label': 'Express delivery',
            'description': 'Faster dispatch when available',
        },
        'pickup': {
            'label': 'Pickup',
            'description': 'Collect from seller / agreed location (no delivery fee)',
        },
    }
    currency = 'TZS'
    try:
        from core.models import SiteConfiguration

        currency = SiteConfiguration.get_solo().default_currency or currency
    except Exception:
        pass

    options = []
    for method in sorted(rates.keys(), key=lambda m: (m != 'standard', m)):
        m = meta.get(method, {'label': method.title(), 'description': ''})
        options.append(
            {
                'method': method,
                'label': m['label'],
                'description': m['description'],
                'fee': str(rates[method]),
                'currency': currency,
            }
        )
    return options
