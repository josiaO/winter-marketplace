from rest_framework import viewsets, mixins, permissions
from rest_framework.response import Response
from django.shortcuts import redirect, get_object_or_404
from .models import ShortLink
from .serializers import ShortLinkSerializer
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes
from rest_framework.permissions import AllowAny
from .throttles import ShortLinkCreateThrottle

class ShortLinkViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = ShortLink.objects.all()
    serializer_class = ShortLinkSerializer
    permission_classes = [permissions.AllowAny] # Allow anyone to shorten URLs for sharing (or limit to auth)
    throttle_classes = [ShortLinkCreateThrottle]

    def create(self, request, *args, **kwargs):
        # Check if target_url already exists properly to avoid duplicate
        target_url = request.data.get('target_url')
        if target_url:
            existing = ShortLink.objects.filter(target_url=target_url).first()
            if existing:
                return Response(ShortLinkSerializer(existing, context={'request': request}).data)
        
        return super().create(request, *args, **kwargs)

@extend_schema(responses={302: OpenApiTypes.NONE}, description="Redirect to target URL.")
@api_view(['GET'])
@permission_classes([AllowAny])
def redirect_view(request, code):
    short_link = get_object_or_404(ShortLink, code=code)
    short_link.visit_count += 1
    short_link.save(update_fields=['visit_count'])
    return redirect(short_link.target_url)
