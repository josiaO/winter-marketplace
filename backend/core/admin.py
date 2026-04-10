from django.contrib import admin

from core.models import OutboxEvent, SiteConfiguration


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'event_name',
        'status',
        'retry_count',
        'created_at',
    )
    list_filter = ('status', 'event_name')
    search_fields = ('event_name', 'last_error')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'support_phone', 'support_email', 'whatsapp_number', 'is_active']
    fieldsets = [
        (None, {
            'fields': ['is_active']
        }),
        ('Support Information', {
            'fields': ['support_phone', 'support_email', 'whatsapp_number']
        }),
        ('Direct Admin Contact', {
            'fields': ['admin_contact_name', 'admin_contact_phone', 'admin_contact_whatsapp']
        }),
    ]

    def has_add_permission(self, request):
        # Only allow one configuration record
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)
