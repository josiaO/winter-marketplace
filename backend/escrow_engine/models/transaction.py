"""
escrow_engine.models.transaction
---------------------------------
Universal Transaction model — the heart of the escrow engine.

This model is intentionally decoupled from commerce.Order.
It supports three sources:
  - marketplace : internal order checkout
  - external    : two parties who found each other outside the platform
  - api         : third-party developer integration

The linked_order field is *optional* and only set when the transaction
originates from the internal marketplace checkout flow.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from escrow_engine.state_machine import TransactionStatus, validate_transition


class TransactionSource:
    MARKETPLACE = 'marketplace'
    EXTERNAL = 'external'
    API = 'api'

    CHOICES = [
        (MARKETPLACE, 'Marketplace'),
        (EXTERNAL, 'External (WhatsApp / Off-Platform)'),
        (API, 'Third-Party API'),
    ]


class Transaction(models.Model):
    """
    Universal escrow transaction.

    Works for:
      • Internal marketplace orders (linked_order is set)
      • External payment link flows (buyer_phone / seller_phone used)
      • Third-party API integrations (source='api', external_reference set)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Human-readable unique reference (e.g. "TXN-20240101-ABCD")
    reference = models.CharField(max_length=64, unique=True, db_index=True)

    # ── Money ─────────────────────────────────────────────────────────────────
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='TZS')

    # ── State ─────────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.CREATED,
        db_index=True,
    )

    # ── Source ────────────────────────────────────────────────────────────────
    source = models.CharField(
        max_length=20,
        choices=TransactionSource.CHOICES,
        default=TransactionSource.MARKETPLACE,
        db_index=True,
    )

    # ── Parties (internal users — nullable for external flows) ────────────────
    buyer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='escrow_buyer_transactions',
        help_text=_("Registered buyer. Null for external/anonymous flows."),
    )
    seller_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='escrow_seller_transactions',
        help_text=_("Registered seller. Null for external flows."),
    )

    # ── Parties (external contacts — phone/email for WhatsApp / off-platform) ─
    buyer_phone = models.CharField(max_length=30, blank=True)
    buyer_email = models.EmailField(blank=True)
    seller_phone = models.CharField(max_length=30, blank=True)
    seller_email = models.EmailField(blank=True)

    # ── External Reference (for third-party API integrations) ─────────────────
    external_reference = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text=_("Reference from developer API caller's system."),
    )

    created_by_api_key = models.ForeignKey(
        'escrow_engine.APIKey',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='transactions',
        help_text=_("Developer API key that created this transaction (if any)."),
    )

    # ── Payment gateway trace ─────────────────────────────────────────────────
    payment_method = models.CharField(
        max_length=50, blank=True,
        help_text=_("mpesa, selcom, stripe, bank_transfer, etc."),
    )
    gateway_reference = models.CharField(
        max_length=255, blank=True,
        help_text=_("Transaction ID returned by the payment gateway."),
    )
    gateway_payload = models.JSONField(
        null=True, blank=True,
        help_text=_("Raw response from payment gateway for debugging."),
    )

    # ── Optional link to marketplace Order ────────────────────────────────────
    linked_order = models.OneToOneField(
        'commerce.Order',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='engine_transaction',
        help_text=_("Set when this transaction originates from a marketplace order. "
                    "Null for external/API transactions."),
    )

    # ── Dispute resolution shortcut ───────────────────────────────────────────
    dispute_resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='escrow_disputes_resolved',
    )
    dispute_reason = models.TextField(blank=True)

    # ── Metadata ──────────────────────────────────────────────────────────────
    description = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text=_("Arbitrary key/value data from source system."),
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    held_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    # ── Expiry & Release ──────────────────────────────────────────────────────
    auto_release_at = models.DateTimeField(
        null=True, blank=True,
        help_text=_("When funds will be automatically released to the seller if no dispute is raised.")
    )
    preferred_provider = models.CharField(
        max_length=50, blank=True,
        help_text=_("Explicitly override the payment provider for this transaction.")
    )

    class Meta:
        app_label = 'escrow_engine'
        verbose_name = _('Transaction')
        verbose_name_plural = _('Transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['source', 'status']),
            models.Index(fields=['buyer_user', '-created_at']),
            models.Index(fields=['seller_user', '-created_at']),
            models.Index(fields=['gateway_reference']),
        ]

    def __str__(self):
        return f"Transaction {self.reference} [{self.status}] {self.amount} {self.currency}"

    def clean(self):
        super().clean()
        # Only validate transitions for existing records.
        # self._state.adding is True for new records even if pk is set (e.g. UUID).
        if not self._state.adding and self.pk:
            try:
                old = Transaction.objects.only('status').get(pk=self.pk)
                validate_transition(old.status, self.status)
            except Transaction.DoesNotExist:
                # This could happen if pk was set manually but not yet saved
                pass

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_reference()
        self.clean()
        super().save(*args, **kwargs)

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _generate_reference() -> str:
        from django.utils import timezone
        import random, string
        now = timezone.now()
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"TXN-{now.strftime('%Y%m%d')}-{suffix}"

    def transition_to(self, new_status: str, actor=None, actor_label: str = '', reason: str = '') -> 'Transaction':
        """
        Safely transition to a new status and append an audit log entry.
        Returns self for chaining.
        """
        from escrow_engine.models.audit import TransactionLog
        from django.utils import timezone
        from django.contrib.auth import get_user_model

        User = get_user_model()
        actor_user = actor if isinstance(actor, User) else None
        label = actor_label or (actor if isinstance(actor, str) else '')

        validate_transition(self.status, new_status)
        old_status = self.status
        self.status = new_status

        # Set convenience timestamps
        now = timezone.now()
        if new_status == TransactionStatus.HOLD:
            self.held_at = now
            # Default auto-release: 7 days
            if not self.auto_release_at:
                self.auto_release_at = now + timezone.timedelta(days=7)
        elif new_status == TransactionStatus.RELEASED:
            self.released_at = now
        elif new_status == TransactionStatus.REFUNDED:
            self.refunded_at = now

        # Use update_fields to skip full clean() re-validation of the new persisted state
        fields = ['status', 'updated_at', 'held_at', 'released_at', 'refunded_at', 'auto_release_at']
        Transaction.objects.filter(pk=self.pk).update(
            status=new_status,
            held_at=self.held_at,
            released_at=self.released_at,
            refunded_at=self.refunded_at,
            auto_release_at=self.auto_release_at,
            updated_at=now,
        )
        self.refresh_from_db()

        TransactionLog.objects.create(
            transaction=self,
            from_status=old_status,
            to_status=new_status,
            actor_user=actor_user,
            actor_label=label,
            reason=reason,
        )
        return self

    def link_order(self, order) -> None:
        """Attach a marketplace Order to this transaction."""
        Transaction.objects.filter(pk=self.pk).update(linked_order=order)
        self.linked_order = order

    @property
    def buyer_display(self) -> str:
        if self.buyer_user:
            return self.buyer_user.get_full_name() or self.buyer_user.username
        return self.buyer_phone or self.buyer_email or 'Unknown Buyer'

    @property
    def seller_display(self) -> str:
        if self.seller_user:
            return self.seller_user.get_full_name() or self.seller_user.username
        return self.seller_phone or self.seller_email or 'Unknown Seller'
