"""
escrow_engine.models.payment_record
-------------------------------------
PaymentRecord — raw gateway interaction log.

This is the low-level record of each individual payment attempt
(STK push, card charge, reversal, etc.).  It is NOT business logic.
It is a receipt attached to a Transaction.

Multiple PaymentRecords can exist per Transaction (for retries).
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class PaymentRecordStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    COMPLETED = 'completed', _('Completed')
    FAILED = 'failed', _('Failed')
    REVERSED = 'reversed', _('Reversed')


class PaymentRecord(models.Model):
    """
    Raw record of a single payment gateway interaction.

    Replaces the old transactions.Transaction model.
    Stores one row per gateway call: initiations, confirmations, refunds.
    """

    # Keep as alias for backward compat
    Status = PaymentRecordStatus

    # Parent transaction
    transaction = models.ForeignKey(
        'escrow_engine.Transaction',
        on_delete=models.CASCADE,
        related_name='payment_records',
        null=True, blank=True,
        help_text=_("Engine transaction this record belongs to. "
                    "Null for legacy records attached via order."),
    )

    # Legacy order link (backward compat — new code uses transaction instead)
    order = models.ForeignKey(
        'commerce.Order',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='payment_records',
    )

    provider = models.CharField(
        max_length=50,
        default='selcom',
        help_text=_("mpesa, selcom, stripe, bank_transfer, etc."),
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='TZS')
    status = models.CharField(max_length=20, choices=PaymentRecordStatus.choices, default=PaymentRecordStatus.PENDING, db_index=True)

    # Gateway trace
    reference = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text=_("Transaction ID returned by the payment gateway."),
    )
    raw_payload = models.JSONField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='payment_records',
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'escrow_engine'
        verbose_name = _('Payment Record')
        verbose_name_plural = _('Payment Records')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"PaymentRecord {self.reference or self.pk} [{self.status}] {self.amount} {self.currency}"
