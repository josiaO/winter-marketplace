from django.contrib import admin
from .models import Conversation, Message, Notification, SupportRequest


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'seller', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__username', 'seller__username']
    
    # participants removed, user/agent are FKs


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'sender', 'text_preview', 'read_at', 'has_attachment', 'created_at']
    list_filter = ['read_at', 'created_at']
    search_fields = ['sender__username', 'text', 'conversation__user__username', 'conversation__seller__username']
    readonly_fields = ['created_at']
    
    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Text Preview'
    
    def has_attachment(self, obj):
        return bool(obj.attachment)
    has_attachment.boolean = True
    has_attachment.short_description = 'Attachment'





@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'type', 'title', 'is_read', 'created_at']
    list_filter = ['is_read', 'type', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    readonly_fields = ['id', 'created_at']


@admin.register(SupportRequest)
class SupportRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'subject', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'subject', 'message']
    readonly_fields = ['id', 'user', 'created_at', 'updated_at']
    fieldsets = [
        (None, {
            'fields': ['id', 'user', 'subject', 'message', 'status']
        }),
        ('Admin Actions', {
            'fields': ['admin_notes']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at']
        }),
    ]
