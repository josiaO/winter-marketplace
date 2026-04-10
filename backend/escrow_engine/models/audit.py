"""
escrow_engine.models.audit
---------------------------
Immutable audit log — one row per status transition on a Transaction.
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class TransactionLog(models.Model):
    """Append-only audit log for Transaction state changes."""

    transaction = models.ForeignKey(
        'escrow_engine.Transaction',
        on_delete=models.CASCADE,
        related_name='logs',
    )
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    reason = models.TextField(blank=True)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='escrow_audit_actions',
        help_text=_("User who triggered the transition. Null for system/async actions."),
    )
    actor_label = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("System label for the actor (e.g. 'System', 'Celery: auto-release', 'Buyer').")
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'escrow_engine'
        verbose_name = _('Transaction Log')
        verbose_name_plural = _('Transaction Logs')
        ordering = ['-created_at']

    def __str__(self):
        actor = self.actor_label or (self.actor_user.username if self.actor_user else 'System')
        return (
            f"[{self.transaction.reference}] "
            f"{self.from_status} → {self.to_status} "
            f"by {actor} @ {self.created_at:%Y-%m-%d %H:%M}"
        )
