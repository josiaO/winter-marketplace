from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from cloudinary.models import CloudinaryField
from .constants import (
    MessageStatus,
    SupportRequestStatus
)
import uuid

User = get_user_model()


class Conversation(models.Model):
    """
    Conversation model linked to Order, Listing, or Dispute.
    Supports marketplace communication between buyers and sellers.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations_as_user')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations_as_seller')
    
    # Context links - conversation can be related to one of these
    order = models.ForeignKey('commerce.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations', help_text="Order context")
    listing = models.ForeignKey('listings.Listing', on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations', help_text="Listing context")
    dispute = models.ForeignKey('escrow_engine.Dispute', on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations', help_text="Dispute context")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'communications'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['order', '-updated_at']),
            models.Index(fields=['listing', '-updated_at']),
            models.Index(fields=['dispute', '-updated_at']),
        ]
    
    hidden_by = models.ManyToManyField(User, related_name='hidden_conversations', blank=True)

    def __str__(self):
        context = []
        if self.order:
            context.append(f"Order: #{self.order.id}")
        if self.listing:
            context.append(f"Listing: {self.listing.title}")
        if self.dispute:
            context.append(f"Dispute: #{self.dispute.id}")
        context_str = ", ".join(context) if context else "No Context"
        return f"Conversation: {self.user.username} - {self.seller.username} ({context_str})"
    
    def get_context(self):
        """Get the primary context object for this conversation"""
        if self.order:
            return {'type': 'order', 'object': self.order}
        elif self.listing:
            return {'type': 'listing', 'object': self.listing}
        elif self.dispute:
            return {'type': 'dispute', 'object': self.dispute}
        return None


class Message(models.Model):
    STATUS_SENT = MessageStatus.SENT
    STATUS_DELIVERED = MessageStatus.DELIVERED
    STATUS_READ = MessageStatus.READ
    
    STATUS_CHOICES = MessageStatus.choices
    
    # Core fields
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()  # Legacy plaintext field
    text_encrypted = models.TextField(null=True, blank=True)  # Encrypted message content
    is_encrypted = models.BooleanField(default=False)  # Flag to indicate if message is encrypted
    attachment = CloudinaryField("attachment", resource_type="auto", null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)  # NEW: When message was delivered
    read_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Message state
    status = models.CharField(
        max_length=10,
        choices=MessageStatus.choices,
        default=STATUS_SENT,
        db_index=True,  # Index for efficient queries on undelivered messages
        help_text="Message delivery state: sent → delivered → read"
    )
    
    # Related objects
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    # Soft delete
    is_deleted = models.BooleanField(default=False)
    hidden_by = models.ManyToManyField(User, related_name='hidden_messages', blank=True)

    class Meta:
        ordering = ['created_at']
        app_label = 'communications'
    
    def save(self, *args, **kwargs):
        """Auto-encrypt message text on save"""
        if self.text and not self.is_encrypted:
            try:
                from .encryption import get_encryptor
                encryptor = get_encryptor()
                self.text_encrypted = encryptor.encrypt(self.text)
                self.is_encrypted = True
                # Clear plaintext after encryption to prevent data remanence
                # The decrypted_text property will be used to access the message
                self.text = ""
            except Exception as e:
                # Log error but don't fail the save
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to encrypt message: {e}")
        super().save(*args, **kwargs)
    
    @property
    def decrypted_text(self):
        """Get decrypted message text"""
        if self.is_encrypted and self.text_encrypted:
            try:
                from .encryption import get_encryptor
                encryptor = get_encryptor()
                return encryptor.decrypt(self.text_encrypted)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to decrypt message: {e}")
                return "[Encrypted message]"
        return self.text

    def mark_delivered(self):
        """Mark message as delivered (✓✓)"""
        from django.utils import timezone
        if self.status == self.STATUS_SENT:
            self.status = self.STATUS_DELIVERED
            self.delivered_at = timezone.now()
            self.save(update_fields=['status', 'delivered_at'])
            return True
        return False
    
    def mark_read(self):
        """Mark message as read (✓✓ blue)"""
        from django.utils import timezone
        if self.status in [self.STATUS_SENT, self.STATUS_DELIVERED]:
            self.status = self.STATUS_READ
            self.read_at = timezone.now()
            # If never delivered, set delivered_at to same time as read_at
            if not self.delivered_at:
                self.delivered_at = self.read_at
            self.save(update_fields=['status', 'read_at', 'delivered_at'])
            return True
        return False
    
    @property
    def is_read(self):
        """Check if message has been read"""
        return self.status == self.STATUS_READ
    
    def __str__(self):
        return f"Message from {self.sender.username} ({self.status})"








# Models from notifications app
class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=50)  # message, visit, support, update
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Generic relation fields for linking to any object (Message, Visit, etc)
    related_object_id = models.IntegerField(null=True, blank=True)
    # Storing type string instead of ContentType for simplicity as per request
    related_object_type = models.CharField(max_length=50, null=True, blank=True)
    
    # Keeping 'data' field for extra flexibility if needed, though not in strict request, it's safer to keep for backward compat or extra payload
    data = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        app_label = 'communications'

    def __str__(self):
        return f"{self.type}: {self.title}"


class DeviceToken(models.Model):
    PLATFORM_CHOICES = [
        ('web', 'Web'),
        ('android', 'Android'),
        ('ios', 'iOS'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='web')
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'communications'
        verbose_name = 'Device Token'
        verbose_name_plural = 'Device Tokens'

    def __str__(self):
        return f"{self.user.username} - {self.platform} token"


class SupportRequest(models.Model):
    STATUS_PENDING = SupportRequestStatus.PENDING
    STATUS_IN_PROGRESS = SupportRequestStatus.IN_PROGRESS
    STATUS_RESOLVED = SupportRequestStatus.RESOLVED
    STATUS_CLOSED = SupportRequestStatus.CLOSED

    STATUS_CHOICES = SupportRequestStatus.choices

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_requests')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=SupportRequestStatus.choices, default=STATUS_PENDING)
    admin_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'communications'
        ordering = ['-created_at']

    def __str__(self):
        return f"Support Request #{self.id} - {self.subject} ({self.status})"
