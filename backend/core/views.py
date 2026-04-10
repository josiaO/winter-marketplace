from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import SiteConfiguration
from .serializers.settings import SiteConfigurationSerializer

class SiteConfigurationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing and editing site configuration.
    Non-admins can only read the active configuration.
    """

    queryset = SiteConfiguration.objects.filter(is_active=True)
    serializer_class = SiteConfigurationSerializer

    def get_authenticators(self):
        # Public read must not run JWT/Firebase auth: a stale Bearer token would
        # return 403 (token_not_valid) before AllowAny is applied, breaking dashboards.
        # self.request can be unset during drf-spectacular schema introspection (mock request).
        request = getattr(self, "request", None)
        if (
            request is not None
            and getattr(self, "action", None) == "current"
            and request.method.upper() == "GET"
        ):
            return []
        return super().get_authenticators()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    @action(detail=False, methods=['get', 'patch'])
    def current(self, request):
        """Get or update the current active configuration"""
        config = SiteConfiguration.get_solo()
        if request.method == 'PATCH':
            serializer = self.get_serializer(config, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        
        serializer = self.get_serializer(config)
        return Response(serializer.data)
