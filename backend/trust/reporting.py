"""
Abuse report automation: subject resolution, duplicate checks, auto-suspend after threshold.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

OPEN_STATUSES = ('pending', 'under_review')


def resolve_subject_user(*, report_type: str, listing, reported_user, review):
    """
    Return the user account this report is ultimately about (for triage and auto-suspend).
    """
    if report_type == 'user':
        return reported_user
    if report_type == 'listing' and listing is not None and getattr(listing, 'owner_id', None):
        return listing.owner
    if report_type == 'review' and review is not None:
        if reported_user is not None and reported_user.id in (
            review.seller_id,
            review.buyer_id,
        ):
            return reported_user
        return review.seller
    if report_type == 'message':
        return reported_user
    return None


def distinct_open_reporter_count(subject_user, *, since) -> int:
    from .models import Report

    return (
        Report.objects.filter(
            subject_user=subject_user,
            status__in=OPEN_STATUSES,
            created_at__gte=since,
        )
        .values('reporter_id')
        .distinct()
        .count()
    )


def _audit_moderator():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    u = User.objects.filter(is_superuser=True).order_by('pk').first()
    if u:
        return u
    return User.objects.filter(is_staff=True).order_by('pk').first()


def maybe_auto_suspend_for_subject(subject_user, *, new_report) -> bool:
    """
    If open reports from distinct reporters exceed settings threshold, deactivate the subject user.
    Staff/superuser subjects are never auto-suspended.
    Returns True if a suspension was applied.
    """
    if subject_user is None:
        return False
    if not getattr(subject_user, 'is_active', True):
        return False
    if subject_user.is_staff or subject_user.is_superuser:
        return False

    threshold = int(getattr(settings, 'TRUST_REPORT_AUTO_SUSPEND_THRESHOLD', 5))
    lookback_days = int(getattr(settings, 'TRUST_REPORT_LOOKBACK_DAYS', 90))
    if threshold <= 0:
        return False

    since = timezone.now() - timedelta(days=lookback_days)
    count = distinct_open_reporter_count(subject_user, since=since)
    if count < threshold:
        return False

    moderator = _audit_moderator()
    reason = (
        f'Automatic account suspension: {count} distinct reporter(s) filed open abuse reports '
        f'within the last {lookback_days} day(s) (threshold {threshold}). '
        f'Triggering report id={new_report.pk}.'
    )

    with transaction.atomic():
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.filter(pk=subject_user.pk).update(is_active=False)

        from .models import ModerationAction, TrustScore

        if moderator is not None:
            ModerationAction.objects.create(
                moderator=moderator,
                action_type='suspend',
                target_type='user',
                target_user_id=subject_user.pk,
                reason=reason,
            )
        else:
            logger.warning(
                'trust.reporting: auto-suspend applied but no staff user exists for ModerationAction (report %s)',
                new_report.pk,
            )

        score, _ = TrustScore.objects.get_or_create(user_id=subject_user.pk)
        score.violation_count += 1
        score.calculate_score()
        score.save()

    logger.info(
        'trust.reporting: auto-suspended user_id=%s after %s distinct reporters (report %s)',
        subject_user.pk,
        count,
        new_report.pk,
    )
    return True


def evaluate_report_automation(report) -> None:
    """Run after a report is persisted."""
    subject = report.subject_user
    if subject is None:
        return
    maybe_auto_suspend_for_subject(subject, new_report=report)
