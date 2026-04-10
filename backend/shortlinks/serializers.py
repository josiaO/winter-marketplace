from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import ShortLink
from django.conf import settings

class ShortLinkSerializer(serializers.ModelSerializer):
    short_url = serializers.SerializerMethodField()

    class Meta:
        model = ShortLink
        fields = ['id', 'target_url', 'code', 'short_url', 'created_at', 'visit_count']
        read_only_fields = ['id', 'code', 'created_at', 'visit_count', 'short_url']

    @extend_schema_field(serializers.URLField())
    def get_short_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f"/s/{obj.code}")
        return f"{settings.SITE_URL}/s/{obj.code}"
