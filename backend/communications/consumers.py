import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db.models import Q
from communications.models import Conversation, Message
from communications.serializers import MessageSerializer
from communications.notification_service import get_notification_service
from communications.throttles import WebSocketRateLimit
from communications.presence import PresenceManager  # NEW
from rest_framework.exceptions import Throttled

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """Consumer for real-time notifications"""
    
    async def connect(self):
        user = self.scope["user"]
        
        if user.is_anonymous:
            await self.accept()
            await self.send(text_data=json.dumps({
                'type': 'error',
                'code': 'unauthorized',
                'message': 'Authentication failed or token expired'
            }))
            await self.close(code=4001)
            return

        # Add user to their personal notification group
        self.group_name = f"notifications_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        # Set User Online using Redis presence
        await self.set_user_online(user)

    async def disconnect(self, close_code):
        user = self.scope["user"]
        # Remove user from their notification group
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        
        # Set User Offline using Redis presence
        if not user.is_anonymous:
            await self.set_user_offline(user)
    
    @database_sync_to_async
    def set_user_offline(self, user):
        """Set user offline via Redis presence (replacing DB-based approach)"""
        PresenceManager.set_offline(user.id)
        
        # Broadcast to active conversations
        conversations = Conversation.objects.filter(
            Q(user=user) | Q(seller=user),
            is_active=True
        )
        
        channel_layer = get_channel_layer()
        for conv in conversations:
            async_to_sync(channel_layer.group_send)(
                f'chat_{conv.id}',
                {
                    'type': 'user_status',
                    'user_id': user.id,
                    'is_online': False
                }
            )

    async def notification_message(self, event):
        """Send notification to WebSocket (Legacy/Raw)"""
        # Kept for backward compatibility if any other service uses it
        message = event["message"]
        await self.send(text_data=json.dumps(message))

    async def notification(self, event):
        """
        Send notification to WebSocket (Standardized)
        Wraps payload in {type: 'notification', ...} for frontend compatibility
        """
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': event['message']
        }))
    
    @database_sync_to_async
    def set_user_online(self, user):
        """Set user online via Redis presence - OPTIMIZED with debouncing"""
        # Only set online and broadcast if user was NOT already online (debounced)
        was_online = PresenceManager.is_online(user.id)
        PresenceManager.set_online(user.id)
        
        # Skip expensive broadcast if already online (major optimization)
        if was_online:
            return
        
        # Broadcast to active conversations (only if status changed)
        # Use values_list to avoid loading full conversation objects
        conversation_ids = Conversation.objects.filter(
            Q(user=user) | Q(seller=user),
            is_active=True
        ).values_list('id', flat=True)[:20]  # Limit to 20 most recent
        
        channel_layer = get_channel_layer()
        for conv_id in conversation_ids:
            async_to_sync(channel_layer.group_send)(
                f'chat_{conv_id}',
                {
                    'type': 'user_status',
                    'user_id': user.id,
                    'is_online': True
                }
            )


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rate_limiter = WebSocketRateLimit(max_messages=10, window=10)
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.conversation_group_name = f'chat_{self.conversation_id}'
        
        if not self.user.is_authenticated:
            await self.accept()
            await self.send(text_data=json.dumps({
                'type': 'error',
                'code': 'unauthorized',
                'message': 'Authentication failed or token expired'
            }))
            await self.close(code=4001)
            return
        
        # Verify user is participant
        is_participant = await self.verify_participant()
        if not is_participant:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.conversation_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Mark conversation as active
        await self.mark_conversation_active()
        
        # Send initial status of other participant
        status_data = await self.get_initial_status()
        if status_data:
            await self.send(text_data=json.dumps({
                'type': 'user_status',
                'user_id': status_data['user_id'],
                'is_online': status_data['is_online']
            }))
        
        logger.info(f"User {self.user.username} connected to conversation {self.conversation_id}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.conversation_group_name,
            self.channel_name
        )
        logger.info(f"User {self.user.username} disconnected from conversation {self.conversation_id}")
    
    async def receive(self, text_data):
        """Handle incoming message"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')
            
            if message_type == 'message':
                await self.handle_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'delivered':  # NEW: Delivery receipt
                await self.handle_delivery_receipt(data)
            elif message_type == 'read':
                await self.handle_read_receipt(data)
            elif message_type == 'heartbeat':  # NEW: Presence heartbeat
                await self.handle_heartbeat(data)
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            await self.send_error("Invalid message format")
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self.send_error(str(e))
    
    async def handle_message(self, data):
        """Handle new message with rate limiting and lifecycle tracking"""
        try:
            # Check rate limit first
            await self.check_rate_limit()
            
            text = data.get('text', '').strip()
            # If front-end sends 'content', support that too for compatibility
            if not text:
                 text = data.get('content', '').strip()

            property_id = data.get('property_id')

            if not text and not property_id:
                return
            
            # Save message to database (status defaults to 'sent')
            message = await self.save_message(text, property_id)
            
            # Pre-fetch all related data to avoid N+1 queries during serialization
            # This is critical for performance when broadcasting to multiple users
            message = await database_sync_to_async(
                Message.objects.select_related('sender__profile').get
            )(id=message.id)
            
            # Serialize message data with pre-fetched relationships
            message_data = await self.serialize_message(message)
            
            # Send confirmation to sender (message_sent event)
            await self.send(text_data=json.dumps({
                'type': 'message_sent',
                'message': message_data,
            }))
            
            # Broadcast to ALL participants in group (including sender)
            await self.channel_layer.group_send(
                self.conversation_group_name,
                {
                    'type': 'chat.message',
                    'message': message_data,
                    'sender_id': self.user.id,
                }
            )
            
            # Send push notification to offline participants
            await self.notify_participants(message)
            
        except Throttled as e:
            logger.warning(f"Rate limit exceeded for user {self.user.id} in conversation {self.conversation_id}")
            await self.send_error(f"Rate limit exceeded. Please wait {int(e.wait)} seconds.")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await self.send_error("Failed to send message")
    
    async def handle_typing(self, data):
        """Handle typing indicator"""
        is_typing = data.get('is_typing', False)
        
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {
                'type': 'typing.indicator',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_typing': is_typing,
            }
        )
    
    async def handle_delivery_receipt(self, data):
        """Handle message delivery receipt (NEW)"""
        message_id = data.get('message_id')
        if message_id:
            success = await self.mark_message_delivered(message_id)
            if success:
                await self.broadcast_status_update(message_id, Message.STATUS_DELIVERED)
    
    async def handle_read_receipt(self, data):
        """Handle message read receipt (ENHANCED)"""
        message_id = data.get('message_id')
        if message_id:
            success = await self.mark_message_read(message_id)
            if success:
                await self.broadcast_status_update(message_id, Message.STATUS_READ)
    
    async def handle_heartbeat(self, data):
        """Handle presence heartbeat to keep user online (NEW)"""
        await self.refresh_presence()
    
    # Event handlers
    async def chat_message(self, event):
        """Send message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket"""
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'username': event['username'],
                'is_typing': event['is_typing'],
            }))
    
    async def notification(self, event):
        """Send notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': event['message'],
            'severity': event.get('severity', 'info'),
        }))

    async def user_status(self, event):
        """Send user status update to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'user_id': event['user_id'],
            'is_online': event['is_online']
        }))
    
    # Database operations
    @database_sync_to_async
    def verify_participant(self):
        """Verify user is a participant in the conversation"""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            return self.user == conversation.user or self.user == conversation.seller
        except Conversation.DoesNotExist:
            return False
    
    @database_sync_to_async
    def save_message(self, text, property_id=None):
        """Save message to database with optimized query"""
        # Create message with all fields in one go if possible, or update efficiently
        message = Message(
            conversation_id=self.conversation_id,
            sender=self.user,
            text=text
        )
        message.save()
        return message

    @database_sync_to_async
    def serialize_message(self, message):
        """Fast lightweight serialization for real-time messages (Matches DRF structure)"""
        
        property_data = None

        # CRITICAL: Use decrypted_text for encrypted messages (text field is cleared after encryption)
        message_text = message.decrypted_text if message.is_encrypted else message.text

        return {
            'id': message.id,
            'sender': message.sender_id,
            'sender_name': self.user.username if message.sender_id == self.user.id else message.sender.username,
            'sender_role': 'agent' if hasattr(message.sender, 'groups') and message.sender.groups.filter(name='agents').exists() else 'user',
            'sender_avatar': message.sender.profile.image.url if hasattr(message.sender, 'profile') and message.sender.profile.image else None,
            'text': message_text,
            'status': message.status,
            'delivered_at': message.delivered_at.isoformat() if message.delivered_at else None,
            'read_at': message.read_at.isoformat() if message.read_at else None,
            'created_at': message.created_at.isoformat(),
            'property_attachment': property_data,
            'attachment': message.attachment.url if message.attachment else None,
            'is_deleted': message.is_deleted,
        }
    
    @database_sync_to_async
    def mark_conversation_active(self):
        """Mark conversation as active"""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            conversation.is_active = True
            conversation.save()
        except Conversation.DoesNotExist:
            logger.error(f"Conversation {self.conversation_id} not found")
    
    @database_sync_to_async
    def mark_message_delivered(self, message_id):
        """Mark message as delivered (NEW)"""
        try:
            message = Message.objects.get(id=message_id)
            # Only mark as delivered if I'm NOT the sender
            if message.sender != self.user:
                return message.mark_delivered()
            return False
        except Message.DoesNotExist:
            return False
    
    @database_sync_to_async
    def mark_message_read(self, message_id):
        """Mark message as read (ENHANCED - uses new helper method)"""
        try:
            message = Message.objects.get(id=message_id)
            # Only mark as read if I'm NOT the sender
            if message.sender != self.user:
                return message.mark_read()
            return False
        except Message.DoesNotExist:
            return False
    
    async def broadcast_status_update(self, message_id, status):
        """Broadcast message status update to group (NEW)"""
        from django.utils import timezone
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {
                'type': 'status.update',
                'message_id': message_id,
                'status': status,
                'user_id': self.user.id,
                'timestamp': timezone.now().isoformat(),
            }
        )
    
    async def broadcast_read_receipt(self, message_id):
        """Broadcast read receipt to group"""
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {
                'type': 'read.receipt',
                'message_id': message_id,
                'user_id': self.user.id,
            }
        )
    
    async def status_update(self, event):
        """Send status update to WebSocket (NEW)"""
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'message_id': event['message_id'],
            'status': event['status'],
            'user_id': event['user_id'],
            'timestamp': event['timestamp'],
        }))
    
    @database_sync_to_async
    def get_other_participant(self):
        """Get other participant in conversation"""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            return conversation.agent if conversation.user == self.user else conversation.user
        except Conversation.DoesNotExist:
            return None
    
    async def notify_participants(self, message):
        """Send notifications to OFFLINE participants only - OPTIMIZED with caching"""
        try:
            other_participant = await self.get_other_participant()
            if not other_participant:
                return

            # OPTIMIZATION: Cache offline check for 10 seconds to avoid repeated Redis calls
            should_notify = await self.should_send_fcm_cached(other_participant.id)
            
            # Only send push notification if user is OFFLINE
            if should_notify:
                notification_service = get_notification_service()
                if notification_service:
                    from asgiref.sync import sync_to_async
                    content_preview = message.text[:100] if message.text else "Attachment"
                    await sync_to_async(notification_service.notify_new_message)(
                        other_participant,
                        self.user.get_full_name() or self.user.username,
                        content_preview,
                        channels=['push'],  # ONLY push
                        conversation_id=self.conversation_id
                    )
        except Exception as e:
            logger.error(f"Error notifying participants: {e}")
    
    @database_sync_to_async
    def check_user_online(self, user_id):
        """Check if user is online via Redis presence"""
        return PresenceManager.is_online(user_id)
    
    @database_sync_to_async
    def should_send_fcm_cached(self, user_id):
        """Check if FCM should be sent with 10s cache (OPTIMIZATION)"""
        from django.core.cache import cache
        cache_key = f"fcm_check:{user_id}"
        cached = cache.get(cache_key)
        
        if cached is not None:
            return cached == "offline"
        
        # Not cached, check Redis and cache result
        is_offline = not PresenceManager.is_online(user_id)
        cache.set(cache_key, "offline" if is_offline else "online", timeout=10)
        return is_offline
    
    @database_sync_to_async
    def refresh_presence(self):
        """Refresh user's presence TTL (heartbeat)"""
        return PresenceManager.refresh_presence(self.user.id)
    
    @database_sync_to_async
    def get_initial_status(self):
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            other = conversation.agent if conversation.user == self.user else conversation.user
            
            # Check online status via Redis (UPDATED)
            is_online = PresenceManager.is_online(other.id)
                
            return {
                'user_id': other.id,
                'is_online': is_online
            }
        except Exception:
            return None


    
    @database_sync_to_async
    def check_rate_limit(self):
        """Check WebSocket rate limit"""
        return self.rate_limiter.allow_message(self.user.id, self.conversation_id)
    
    async def send_error(self, error_message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': error_message,
        }))



