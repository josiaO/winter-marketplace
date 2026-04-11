"""
escrow_engine.models.payout
----------------------------
Seller payout — created automatically when a transaction is RELEASED.
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


from ..constants import SELCOM_CHANNELS


class PayoutDestination(models.Model):
    """
    Decoupled record of where to send funds for a seller.
    Covers the full Selcom channel set (mobile money, bank, card, Till/QR).
    Can be synced from marketplace.SellerPaymentMethod or set manually
    for external/WhatsApp sellers.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payout_destinations',
    )
    method = models.CharField(
        max_length=20,
        choices=SELCOM_CHANNELS,
        default='mpesa',
        help_text=_("Payment channel via Selcom aggregator.")
    )
    account_number = models.CharField(
        max_length=50,
        help_text=_("Phone number for mobile money; account number for bank; till number for Till/QR.")
    )
    account_name = models.CharField(max_length=100, blank=True)
    bank_code = models.CharField(
        max_length=20, blank=True,
        help_text=_("Selcom bank code (e.g. CRDB, NMB, EQUITY). Required for bank transfers.")
    )
    is_default = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'escrow_engine'
        verbose_name = _('Payout Destination')
        verbose_name_plural = _('Payout Destinations')
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_default=True),
                name='escrow_payoutdest_one_default_per_user',
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.method} ({self.account_number})"


class Payout(models.Model):

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PROCESSING = 'processing', _('Processing')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')

    # Link to the engine transaction (not to Order directly)
    transaction = models.OneToOneField(
        'escrow_engine.Transaction',
        on_delete=models.CASCADE,
        related_name='payout',
    )

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='engine_payouts',
    )

    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='TZS')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    payout_method = models.CharField(
        max_length=50, default='mpesa',
        help_text=_(
            "Selcom channel used for payout: mpesa, tigo_pesa, airtel_money, "
            "halopesa, ezypesa, azampesa, bank, card_visa, card_mastercard, "
            "card_unionpay, till."
        ),
    )
    payout_reference = models.CharField(max_length=255, blank=True)
    failure_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'escrow_engine'
        verbose_name = _('Payout')
        verbose_name_plural = _('Payouts')
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"Payout {self.pk} → {self.seller.username} "
            f"{self.amount} {self.currency} [{self.status}]"
        )
