from rest_framework import serializers
from core.models import SiteConfiguration

class SiteConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteConfiguration
        fields = [
            'id', 'support_phone', 'support_email', 'whatsapp_number',
            'admin_contact_name', 'admin_contact_phone', 'admin_contact_whatsapp',
            'platform_name', 'platform_fee', 'min_listing_price', 'max_listing_price',
            'enable_escrow', 'auto_approve_listings', 'require_phone_verification',
            'require_email_verification', 'enable_push_notifications', 'enable_email_notifications',
            'default_currency', 'default_language', 'is_active', 'logo', 'banner'
        ]
