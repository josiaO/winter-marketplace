"""
Developer API keys — hashed at rest, scoped access.
Allowed scope values: read, write, pay, refund, release.
"""
import hashlib
import hmac
import secrets

from django.db import models
from django.utils.translation import gettext_lazy as _


def hash_api_key(raw_secret: str) -> str:
    """SHA-256 hex digest of the UTF-8 secret (compare with hmac.compare_digest)."""
    return hashlib.sha256(raw_secret.encode('utf-8')).hexdigest()


def verify_api_key(raw_secret: str, stored_hash: str) -> bool:
    if not raw_secret or not stored_hash:
        return False
    candidate = hash_api_key(raw_secret)
    return hmac.compare_digest(candidate, stored_hash)


def generate_api_secret() -> str:
    return secrets.token_urlsafe(32)


class APIKey(models.Model):
    """
    Authenticates the Developer API (X-Api-Key).
    Only key_hash is stored; plaintext is shown once at creation.
    """

    name = models.CharField(max_length=100)
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    # Optional: when non-empty, only these IPs may use the key (REMOTE_ADDR).
    ip_allowlist = models.JSONField(
        default=list,
        blank=True,
        help_text=_('Optional list of IP strings; empty = no restriction.'),
    )
    # Optional per-key override; None = use default developer API throttle only.
    rate_limit_per_minute = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_('Max requests per minute for this key; blank = default throttle.'),
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Key invalid after this time (UTC). Blank = no expiry.'),
    )
    scopes = models.JSONField(
        default=list,
        blank=True,
        help_text=_(
            "List of strings: read, write, pay, refund, release. "
            "read=list/retrieve; write=create transaction + open dispute; "
            "pay/refund/release=matching actions."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'escrow_engine'
        verbose_name = _('API Key')
        verbose_name_plural = _('API Keys')

    def __str__(self):
        return f"{self.name} ({'active' if self.is_active else 'inactive'})"

    def has_scope(self, scope: str) -> bool:
        scopes = self.scopes or []
        return scope in scopes
