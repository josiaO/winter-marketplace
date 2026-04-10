from rest_framework import serializers
from core.models.media import Media

class MediaSerializer(serializers.ModelSerializer):
    url = serializers.FileField(source='file')

    class Meta:
        model = Media
        fields = ['id', 'url', 'media_type', 'is_main', 'order', 'caption', 'created_at']
