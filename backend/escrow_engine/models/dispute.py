"""
escrow_engine.models.dispute
-----------------------------
Dispute and DisputeEvidence — moved from transactions app and upgraded
to operate against the universal Transaction instead of Order.
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class DisputeStatus(models.TextChoices):
    OPEN = 'open', _('Open')
    UNDER_REVIEW = 'under_review', _('Under Review')
    RESOLVED = 'resolved', _('Resolved')
    CLOSED = 'closed', _('Closed')


class Dispute(models.Model):

    # backward-compat alias
    Status = DisputeStatus

    class Resolution(models.TextChoices):
        REFUND_BUYER = 'refund_buyer', _('Refund to Buyer')
        RELEASE_SELLER = 'release_seller', _('Release to Seller')
        PARTIAL_REFUND = 'partial_refund', _('Partial Refund')
        NO_ACTION = 'no_action', _('No Action Required')

    # Primary link: the engine transaction
    transaction = models.OneToOneField(
        'escrow_engine.Transaction',
        on_delete=models.CASCADE,
        related_name='dispute',
        help_text=_("Transaction this dispute is against."),
    )

    # Backward-compat: optional legacy Order link
    legacy_order = models.OneToOneField(
        'commerce.Order',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='engine_dispute',
        help_text=_("Set when dispute originated from a marketplace order. "
                    "Use transaction as primary reference."),
    )

    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='engine_disputes_opened',
        help_text=_("Null for system-generated disputes."),
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=DisputeStatus.choices,
        default=DisputeStatus.OPEN,
        db_index=True,
    )

    # Evidence (denormalized counts for quick display)
    evidence_video = models.FileField(upload_to='engine/disputes/videos/', null=True, blank=True)
    evidence_images_count = models.PositiveIntegerField(default=0)

    # Resolution
    resolution = models.TextField(blank=True)
    resolution_type = models.CharField(
        max_length=20, choices=Resolution.choices, blank=True
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='engine_disputes_resolved',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'escrow_engine'
        verbose_name = _('Dispute')
        verbose_name_plural = _('Disputes')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f"Dispute on {self.transaction.reference} — {self.status}"


class DisputeEvidence(models.Model):
    """Files submitted as part of a dispute (images or video)."""

    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        related_name='evidence',
    )
    file = models.FileField(upload_to='engine/dispute_evidence/')
    media_type = models.CharField(
        max_length=10,
        choices=[('image', 'Image'), ('video', 'Video')],
        default='image',
    )
    caption = models.CharField(max_length=255, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='engine_dispute_evidence',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'escrow_engine'
        verbose_name = _('Dispute Evidence')
        verbose_name_plural = _('Dispute Evidence Items')
