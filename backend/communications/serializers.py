from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Conversation, Message, Notification, DeviceToken, SupportRequest
from accounts.models import Profile
from accounts.roles import get_user_role


# Serializers from messaging app

class MinimalMessageSerializer(serializers.ModelSerializer):
    """Minimal serializer for reply_to field"""
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'sender_name', 'text', 'attachment', 'created_at']

class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    sender_role = serializers.SerializerMethodField()
    sender_avatar = serializers.SerializerMethodField()
    reply_to = MinimalMessageSerializer(read_only=True)
    reply_to_id = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all(), source='reply_to', write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Message
        fields = ['id', 'sender', 'sender_name', 'sender_role', 'sender_avatar', 'text', 'attachment',
                 'status', 'delivered_at', 'read_at', 'is_deleted', 'created_at', 'reply_to', 'reply_to_id']
        read_only_fields = ['sender', 'status', 'delivered_at', 'read_at', 'is_deleted', 'created_at']
    


    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        # Use decrypted text for encrypted messages
        if instance.is_encrypted:
            data['text'] = instance.decrypted_text
        
        # Handle Global Deletion (Delete for Everyone)
        if instance.is_deleted:
            data['text'] = "This message was deleted"
            data['attachment'] = None
            data['is_deleted'] = True
            
        # Handle Deleted User
        try:
            if hasattr(instance.sender, 'profile') and instance.sender.profile.is_deleted:
                data['sender_name'] = "Deleted User"
                data['sender_avatar'] = None
        except Exception:
            pass
            
        return data

    @extend_schema_field(serializers.CharField())
    def get_sender_role(self, obj):
        # ... existing logic ...
        try:
            if hasattr(obj.sender, 'profile') and obj.sender.profile.is_deleted:
                return 'user' # Flatten role for deleted user
            return get_user_role(obj.sender)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error getting sender role: {e}")
            return 'user'
    
    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_sender_avatar(self, obj):
        try:
            # Check if sender exists (it might be None if user was hard deleted, though on_delete=CASCADE usually prevents this)
            if not obj.sender:
                return None
                
            if hasattr(obj.sender, 'profile'):
                if obj.sender.profile.is_deleted:
                    return None
                if obj.sender.profile.image:
                    return obj.sender.profile.image.url
            return None
        except Exception:
            return None
            pass
        return None


class ConversationSerializer(serializers.ModelSerializer):
    other_participant = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    listing_image = serializers.SerializerMethodField()
    listing_summary = serializers.SerializerMethodField()
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    listing_id = serializers.IntegerField(source='listing.id', read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True)
    dispute_id = serializers.IntegerField(source='dispute.id', read_only=True)
    context = serializers.SerializerMethodField()
    participant_name = serializers.SerializerMethodField()
    participant_avatar = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'user', 'seller', 'other_participant',
            'participant_name', 'participant_avatar',
            'order', 'order_id',
            'listing', 'listing_id', 'listing_title', 'listing_image', 'listing_summary',
            'dispute', 'dispute_id',
            'context',
            'last_message', 'unread_count', 'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['user', 'seller', 'created_at', 'updated_at']
    
    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_other_participant(self, obj):
        request = self.context.get('request')
        if request and request.user:
            other_user = obj.seller if request.user == obj.user else obj.user
            if other_user:
                return {
                    'id': other_user.id,
                    'username': other_user.username,
                    'full_name': other_user.get_full_name() or other_user.username,
                    'email': other_user.email,
                    'role': get_user_role(other_user),
                    'avatar': other_user.profile.image.url if hasattr(other_user, 'profile') and other_user.profile.image else None
                }
        return None

    @extend_schema_field(serializers.CharField())
    def get_participant_name(self, obj):
        request = self.context.get('request')
        if request and request.user:
            other_user = obj.seller if request.user == obj.user else obj.user
            if other_user:
                return other_user.get_full_name() or other_user.username
        return "Unknown"

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_participant_avatar(self, obj):
        other = self.get_other_participant(obj)
        return other.get('avatar') if other else None
    
    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_last_message(self, obj):
        # Optimization: use annotated fields if available
        if hasattr(obj, 'last_message_text') and obj.last_message_created_at:
             return {
                'id': None, # We didn't fetch ID in subquery to save space, or we can add it if needed
                'text': obj.last_message_text,
                'sender_id': obj.last_message_sender_id,
                'sender_name': None, # We skipped joining User for sender name to keep it fast
                'created_at': obj.last_message_created_at,
                'is_read': True # simplified for list view
            }

        # Fallback for non-annotated querysets
        request = self.context.get('request')
        qs = obj.messages.all()
        if request and request.user:
            qs = qs.exclude(hidden_by=request.user)
            
        last_msg = qs.order_by('-created_at').first()
        if last_msg:
            # CRITICAL: Use decrypted_text for encrypted messages (text field is cleared after encryption)
            message_text = last_msg.decrypted_text if last_msg.is_encrypted else last_msg.text
            
            return {
                'id': last_msg.id,
                'text': message_text,
                'sender_id': last_msg.sender.id,
                'sender_name': last_msg.sender.username,
                'created_at': last_msg.created_at,
                'is_read': last_msg.is_read if hasattr(last_msg, 'is_read') else (last_msg.read_at is not None)
            }
        return None
    
    @extend_schema_field(serializers.IntegerField())
    def get_unread_count(self, obj):
        # Use annotated count if available
        if hasattr(obj, 'unread_count'):
            return obj.unread_count

        request = self.context.get('request')
        if request and request.user:
            # Count messages not read by the current user (using new status field)
            return obj.messages.filter(
                status__in=[Message.STATUS_SENT, Message.STATUS_DELIVERED]
            ).exclude(sender=request.user).count()
        return 0
    
    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_listing_image(self, obj):
        """Get the main image URL for the listing"""
        if not obj.listing:
            return None
        
        try:
            # Get first ListingMedia image
            first_media = obj.listing.media.first()
            if first_media and first_media.file:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(first_media.file.url)
                return first_media.file.url
        except Exception:
            pass
        return None

    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_listing_summary(self, obj):
        """Rich listing card for chat (product attached to thread)."""
        if not getattr(obj, 'listing_id', None):
            return None
        listing = obj.listing
        if not listing:
            return None
        image_url = self.get_listing_image(obj)
        return {
            'id': listing.id,
            'title': listing.title,
            'price': str(listing.price),
            'currency': listing.currency,
            'status': listing.status,
            'image_url': image_url,
            'delivery_is_free': getattr(listing, 'delivery_is_free', True),
            'delivery_fee': str(listing.delivery_fee) if getattr(listing, 'delivery_fee', None) is not None else None,
        }
    
    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_context(self, obj):
        """Get the primary context object for this conversation"""
        context = obj.get_context()
        if context:
            return {
                'type': context['type'],
                'id': context['object'].id if context['object'] else None,
            }
        return None


class CreateMessageSerializer(serializers.ModelSerializer):
    reply_to_id = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all(), source='reply_to', write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Message
        fields = ['text', 'attachment', 'reply_to_id']
        extra_kwargs = {
            'text': {'required': False},
            'attachment': {'required': False}
        }
    
    def validate(self, data):
        if not data.get('text') and not data.get('attachment'):
            raise serializers.ValidationError("Message must contain text or an attachment.")
        return data

    def create(self, validated_data):
        conversation = self.context['conversation']
        sender = self.context['request'].user
        
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            text=validated_data.get('text', ''),
            attachment=validated_data.get('attachment'),
            reply_to=validated_data.get('reply_to')
        )
        
        return message


# Serializers from notifications app
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user', 'type', 'title', 'message', 'is_read', 'created_at', 'related_object_id', 'related_object_type', 'data']
        read_only_fields = ['id', 'user', 'created_at']





class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'user', 'token', 'platform', 'created_at', 'last_used']
        read_only_fields = ['id', 'user', 'created_at', 'last_used']
        extra_kwargs = {
            'token': {'validators': []}  # Remove UniqueValidator to allow idempotent registration
        }

    def create(self, validated_data):
        user = self.context['request'].user
        # Get or create token to avoid duplicates
        token, created = DeviceToken.objects.get_or_create(
            token=validated_data['token'],
            defaults={
                'user': user,
                'platform': validated_data.get('platform', 'web')
            }
        )
        if not created:
            # Update user if token was already registered by someone else (rare)
            token.user = user
            token.save()
        return token


class SupportRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = SupportRequest
        fields = [
            'id', 'user', 'user_name', 'user_email', 'subject', 'message', 'status',
            'admin_notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'status', 'admin_notes', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
