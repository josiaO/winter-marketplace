"""
Developer API authentication via X-Api-Key header.
Sets request.auth to an APIKey instance; request.user is anonymous.
"""
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from escrow_engine.models import APIKey
from escrow_engine.models.api_key import hash_api_key


class APIKeyAuthentication(BaseAuthentication):
    """
    Expect header: X-Api-Key: <plaintext secret>
    Looks up by SHA-256 hash; updates last_used_at.
    """

    header_name = 'HTTP_X_API_KEY'

    def authenticate(self, request):
        raw = request.headers.get('X-Api-Key')
        if not raw or not raw.strip():
            return None

        digest = hash_api_key(raw.strip())
        try:
            key = APIKey.objects.get(key_hash=digest, is_active=True)
        except APIKey.DoesNotExist:
            raise AuthenticationFailed('Invalid or inactive API key.')

        if key.expires_at and key.expires_at < timezone.now():
            raise AuthenticationFailed('API key has expired.')

        allow = key.ip_allowlist or []
        if allow:
            xff = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')
            client_ip = (xff[0].strip() if xff and xff[0].strip() else '') or (
                request.META.get('REMOTE_ADDR') or ''
            )
            if client_ip not in allow:
                raise AuthenticationFailed('API key not allowed from this IP address.')

        APIKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        key.last_used_at = timezone.now()

        return (AnonymousUser(), key)
