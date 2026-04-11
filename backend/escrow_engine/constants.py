from django.utils.translation import gettext_lazy as _

# Selcom Payout Channels (supported by the gateway)
SELCOM_CHANNELS = (
    # ── Mobile Money ───────────────────────────────────────────────────
    ('mpesa',          'M-PESA (Vodacom)'),
    ('tigo_pesa',      'Tigo Pesa'),
    ('airtel_money',   'Airtel Money'),
    ('halopesa',       'HaloPesa'),
    ('ezypesa',        'EzyPesa'),
    ('azampesa',       'AzamPesa'),
    # ── Banks (via Selcom) ──────────────────────────────────────────
    ('bank',           'Bank Transfer'),
    # ── Cards ────────────────────────────────────────────────────────────────
    ('card_visa',       'Visa'),
    ('card_mastercard',  'Mastercard'),
    ('card_unionpay',    'UnionPay'),
    # ── Selcom Till / TanQR ───────────────────────────────────────────
    ('till',            'Selcom Till / TanQR'),
)

# Mapping for registry logic
SELCOM_CHANNEL_KEYS = {c[0] for c in SELCOM_CHANNELS}
