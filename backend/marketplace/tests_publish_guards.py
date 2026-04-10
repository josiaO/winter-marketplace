"""Tests for progressive onboarding publish rules."""
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import serializers

from marketplace.publish_guards import (
    enforce_marketplace_publish_rules,
    is_transitioning_to_published,
    seller_identity_verified,
)
from trust.models import TrustScore, UserVerification

User = get_user_model()


class TransitionDetectionTests(TestCase):
    def test_new_instance_published_only_when_true_in_data(self):
        assert is_transitioning_to_published(None, {'is_published': True}) is True
        assert is_transitioning_to_published(None, {'is_published': False}) is False
        assert is_transitioning_to_published(None, {}) is False

    def test_update_from_draft_to_live(self):
        inst = Mock(is_published=False)
        assert is_transitioning_to_published(inst, {'is_published': True}) is True

    def test_update_stays_draft(self):
        inst = Mock(is_published=False)
        assert is_transitioning_to_published(inst, {'title': 'x'}) is False

    def test_update_stays_published_without_touching_flag(self):
        inst = Mock(is_published=True)
        assert is_transitioning_to_published(inst, {'title': 'x'}) is False

    def test_unpublish_allowed(self):
        inst = Mock(is_published=True)
        assert is_transitioning_to_published(inst, {'is_published': False}) is False


class IdentityVerifiedTests(TestCase):
    def test_anonymous_false(self):
        assert seller_identity_verified(None) is False

    def test_trust_score_id_flag(self):
        user = User.objects.create_user(username='tv1', password='x')
        TrustScore.objects.create(user=user, id_verified=True)
        assert seller_identity_verified(user) is True

    def test_user_verification_identity(self):
        user = User.objects.create_user(username='tv2', password='x')
        UserVerification.objects.create(user=user, is_identity_verified=True)
        assert seller_identity_verified(user) is True

    def test_user_verification_id_status_verified(self):
        user = User.objects.create_user(username='tv3', password='x')
        UserVerification.objects.create(user=user, id_status='verified')
        assert seller_identity_verified(user) is True


class EnforcePublishRulesTests(TestCase):
    @override_settings(MARKETPLACE_PUBLISH_REQUIRES_IDENTITY_VERIFICATION=True)
    def test_blocks_unverified_seller(self):
        user = User.objects.create_user(username='b1', password='x')
        with self.assertRaises(serializers.ValidationError) as ctx:
            enforce_marketplace_publish_rules(user=user, transitioning_to_published=True)
        self.assertEqual(
            ctx.exception.detail.get('code'),
            'identity_verification_required',
        )

    @override_settings(MARKETPLACE_PUBLISH_REQUIRES_IDENTITY_VERIFICATION=True)
    def test_allows_verified(self):
        user = User.objects.create_user(username='b2', password='x')
        TrustScore.objects.create(user=user, id_verified=True)
        enforce_marketplace_publish_rules(user=user, transitioning_to_published=True)

    @override_settings(MARKETPLACE_PUBLISH_REQUIRES_IDENTITY_VERIFICATION=True)
    def test_noop_when_not_publishing(self):
        user = User.objects.create_user(username='b3', password='x')
        enforce_marketplace_publish_rules(user=user, transitioning_to_published=False)

    @override_settings(MARKETPLACE_PUBLISH_REQUIRES_IDENTITY_VERIFICATION=False)
    def test_respects_disabled_setting(self):
        user = User.objects.create_user(username='b4', password='x')
        enforce_marketplace_publish_rules(user=user, transitioning_to_published=True)

    @override_settings(MARKETPLACE_PUBLISH_REQUIRES_IDENTITY_VERIFICATION=True)
    def test_staff_bypass(self):
        user = User.objects.create_user(username='b5', password='x', is_staff=True)
        enforce_marketplace_publish_rules(user=user, transitioning_to_published=True)
