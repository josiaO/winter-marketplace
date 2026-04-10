"""
escrow_engine.models.payment_link
---------------------------------
PaymentLink — a shareable tokenised URL for any escrow Transaction.
Moved from the standalone payment_links app to centralize financial logic.
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings


class PaymentLink(models.Model):
    """A single-use tokenised payment link backed by an escrow Transaction."""

    # Unique URL token (UUID v4)
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    # The escrow transaction this link will initiate payment for
    transaction = models.ForeignKey(
        'escrow_engine.Transaction',
        on_delete=models.CASCADE,
        related_name='payment_links',
    )

    # Creator — optional; null for API-created links
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='created_payment_links',
    )

    # Expiry (default: 48 hours from creation)
    expires_at = models.DateTimeField()

    # State
    is_used = models.BooleanField(default=False, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    # Optional display fields (pre-populated to show on the payment page)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    # OTP for identity verification before payment (no-login flow)
    otp_code = models.CharField(max_length=8, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    otp_verified = models.BooleanField(default=False)
    buyer_phone_verified = models.CharField(
        max_length=30, blank=True,
        help_text=_("Phone used during OTP verification — becomes the buyer identity."),
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'escrow_engine'
        verbose_name = _('Payment Link')
        verbose_name_plural = _('Payment Links')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token', 'is_used']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"PaymentLink {self.token} → {self.transaction.reference} ({'used' if self.is_used else 'open'})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """A link is valid if it hasn't been used and hasn't expired."""
        return not self.is_used and not self.is_expired

    def get_absolute_url(self) -> str:
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        return f"{frontend_url}/pay/{self.token}"

    def mark_used(self) -> None:
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at', 'updated_at'])
