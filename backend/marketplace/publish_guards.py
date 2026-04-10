"""
Rules for when a marketplace listing may become publicly visible (is_published=True).

Configurable via Django settings / environment (see backend/settings.py).
"""
from __future__ import annotations

from django.conf import settings
from rest_framework import serializers


def is_transitioning_to_published(instance, data: dict) -> bool:
    """
    True when the request would move a listing from unpublished to published.
    New rows: True only if is_published is explicitly set truthy in data.
    """
    if instance is None:
        return bool(data.get('is_published'))
    was = instance.is_published
    if 'is_published' in data:
        will = bool(data['is_published'])
    else:
        will = was
    return will and not was


def seller_identity_verified(user) -> bool:
    """True if trust layer marks ID verified (admin-approved identity)."""
    if not user or not user.is_authenticated:
        return False

    try:
        sp = user.seller_profile
        if sp.verification_status == 'verified':
            return True
    except Exception:
        pass

    from trust.models import TrustScore, UserVerification

    if TrustScore.objects.filter(user_id=user.pk, id_verified=True).exists():
        return True

    uv = (
        UserVerification.objects.filter(user_id=user.pk)
        .only('is_identity_verified', 'id_status')
        .first()
    )
    if uv is None:
        return False
    if uv.is_identity_verified:
        return True
    return uv.id_status == 'verified'


def enforce_marketplace_publish_rules(*, user, transitioning_to_published: bool) -> None:
    """
    Raise serializers.ValidationError if publish is not allowed.
    No-op if not transitioning to published, if feature is disabled, or if staff/superuser.
    """
    if not transitioning_to_published:
        return

    if not getattr(
        settings,
        'MARKETPLACE_PUBLISH_REQUIRES_IDENTITY_VERIFICATION',
        True,
    ):
        return

    if user and (getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)):
        return

    if seller_identity_verified(user):
        return

    raise serializers.ValidationError(
        {
            'is_published': [
                'Complete identity verification before publishing. '
                'Your listing can stay saved as a draft until then.',
            ],
            'code': 'identity_verification_required',
        }
    )
