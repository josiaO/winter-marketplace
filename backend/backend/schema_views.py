"""
OpenAPI / docs views: when DEBUG=False, require staff to reduce reconnaissance surface.

SessionAuthentication is included so browser-based staff can open ReDoc after Django admin login
(even though API defaults omit session auth in production).
"""
from django.conf import settings
from django.utils.module_loading import import_string
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser


def _resolved_authentication_classes():
    paths = settings.REST_FRAMEWORK.get('DEFAULT_AUTHENTICATION_CLASSES') or []
    return [import_string(p) for p in paths]


_base = _resolved_authentication_classes()
_staff_schema_auth = [SessionAuthentication] + [c for c in _base if c is not SessionAuthentication]


class StaffSpectacularAPIView(SpectacularAPIView):
    authentication_classes = _staff_schema_auth
    permission_classes = [IsAdminUser]


class StaffSpectacularRedocView(SpectacularRedocView):
    authentication_classes = _staff_schema_auth
    permission_classes = [IsAdminUser]
