"""
Gateway webhook idempotency — one row per provider event_id.
"""
from __future__ import annotations

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class GatewayEvent(models.Model):
    """
    Deduplicates inbound webhooks per (provider, event_id).
    Safe under retries and multi-instance workers.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PROCESSED = 'processed', _('Processed')
        DUPLICATE = 'duplicate', _('Duplicate')
        FAILED = 'failed', _('Failed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=50, db_index=True)
    event_id = models.CharField(max_length=255)
    transaction = models.ForeignKey(
        'escrow_engine.Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gateway_events',
    )
    payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'escrow_engine'
        verbose_name = _('Gateway event')
        verbose_name_plural = _('Gateway events')
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'event_id'],
                name='escrow_gatewayevent_provider_event_id_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['provider', 'status']),
        ]

    def __str__(self):
        return f'{self.provider}:{self.event_id[:32]}… [{self.status}]'
