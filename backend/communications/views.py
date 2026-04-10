from rest_framework import viewsets, status, permissions, filters, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiTypes, inline_serializer
from django.db.models import Q
from rest_framework.exceptions import MethodNotAllowed
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import (
    ConversationSerializer, MessageSerializer, CreateMessageSerializer,
    NotificationSerializer, DeviceTokenSerializer, SupportRequestSerializer
)
from .models import Conversation, Message, Notification, DeviceToken, SupportRequest
from communications.notification_service import get_notification_service
from .throttles import MessageRateThrottle, ConversationRateThrottle
from listings.models import Listing
from commerce.models import Order
from escrow_engine.models import Dispute
from django.contrib.auth import get_user_model
from django.db import transaction
import logging
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models import Subquery, OuterRef, Count, Case, When, Value, IntegerField, CharField, F
from communications.firestore_service import get_firestore_service
from .tasks import post_message_side_effects_task, notify_new_conversation_task

logger = logging.getLogger(__name__)


# Views from messaging app
class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__username', 'seller__username']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']
    pagination_class = None
    http_method_names = ['get', 'head', 'options', 'post', 'patch', 'put', 'delete']
    
    def get_throttles(self):
        """Apply specific throttles based on action"""
        if self.action == 'send_message':
            return [MessageRateThrottle()]
        elif self.action == 'start_conversation':
            return [ConversationRateThrottle()]
        return super().get_throttles()
    
    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed('POST', detail="Use the 'start_conversation' endpoint to begin a conversation.")

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PUT')

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PATCH')


    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Conversation.objects.none()
        user = self.request.user
        
        # Subquery for last message details
        last_msg_qs = Message.objects.filter(
            conversation=OuterRef('pk')
        ).exclude(hidden_by=user).order_by('-created_at')

        queryset = Conversation.objects.filter(
            Q(user=user) | Q(seller=user)
        ).select_related('user', 'seller', 'listing')

        # Annotate last message fields
        queryset = queryset.annotate(
            last_message_text=Subquery(last_msg_qs.values('text')[:1]),
            last_message_created_at=Subquery(last_msg_qs.values('created_at')[:1]),
            last_message_sender_id=Subquery(last_msg_qs.values('sender_id')[:1]),
             # We can also get sender username if needed, but sender_id is usually enough to know if it's "me" or "them"
            unread_count=Count(
                'messages',
                filter=Q(
                    messages__status__in=[Message.STATUS_SENT, Message.STATUS_DELIVERED],
                    messages__read_at__isnull=True
                ) & ~Q(messages__sender=user)
            )
        )
        
        if self.action == 'list':
            queryset = queryset.exclude(hidden_by=user)
            
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def _is_participant(self, user, conversation):
        return user == conversation.user or user == conversation.seller
    
    def _get_other_participant(self, user, conversation):
        return conversation.seller if conversation.user == user else conversation.user

    @action(detail=True, methods=['get', 'post'])
    def messages(self, request, pk=None):
        """Get or send messages in a conversation"""
        if request.method == 'POST':
            return self.send_message(request, pk)
        try:
            conversation = self.get_object()
            if not self._is_participant(request.user, conversation):
                 return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            # Optimization: Limit to last 300 messages to prevent memory overload
            # Frontend expects a list, so we slice the queryset.
            # We want the LAST 300 messages (most recent), but order_by is 'created_at' (oldest first).
            # So we take the last 300 from the queryset.
            # Generic slicing [start:end] on queryset works but negative indexing might not supported by all DB backends on sliced qs?
            # Safe way: order by -created_at, take 300, then reverse locally OR subquery.
            # Actually, we can just take the last 300 using python list conversion if dataset is small, but that fetches all.
            # Better: queryset.order_by('-created_at')[:300] then reverse in python.
            # Filter out messages hidden by the user
            messages_qs = conversation.messages.exclude(hidden_by=request.user).order_by('-created_at')[:300]
            messages = reversed(messages_qs)
            serializer = MessageSerializer(messages, many=True, context=self.get_serializer_context())
            
            # Mark messages as read for the current user (messages sent by OTHER party)
            conversation.messages.filter(
                read_at__isnull=True
            ).exclude(sender=request.user).update(read_at=timezone.now())
            
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return Response(
                {'error': 'Failed to fetch messages'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send a message in a conversation"""
        try:
            conversation = self.get_object()
            
            # Ensure sender is a participant in the conversation
            if not self._is_participant(request.user, conversation):
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = CreateMessageSerializer(
                data=request.data,
                context={'conversation': conversation, 'request': request}
            )
            
            if serializer.is_valid():
                message = serializer.save()
                
                # Unhide conversation for BOTH participants when new message arrives
                # This ensures conversations reappear for both sender and receiver
                conversation.hidden_by.clear()
                
                other_participant = self._get_other_participant(request.user, conversation)
                sender_name = request.user.get_full_name() or request.user.username
                # After save(), plaintext may be cleared when encryption is on — use decrypted_text
                body = message.decrypted_text if getattr(message, 'is_encrypted', False) else (message.text or '')
                content_preview = (body[:100] if body else None) or ("Attachment" if message.attachment else "New message")

                message_payload = MessageSerializer(message, context=self.get_serializer_context()).data

                # Broadcast to WebSocket group (keep synchronous for instant UI)
                try:
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f'chat_{conversation.id}',
                        {
                            'type': 'chat.message',
                            'message': message_payload,
                            'sender_id': request.user.id,
                        }
                    )
                except Exception as ws_error:
                    logger.error(f"WebSocket broadcast failed: {ws_error}")

                # Defer email/push/Firestore so POST /messages/ returns quickly
                def queue_side_effects():
                    try:
                        from communications.tasks import post_message_side_effects_task

                        post_message_side_effects_task.delay(
                            message.id,
                            other_participant.id,
                            sender_name,
                            content_preview,
                            conversation.id,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Celery dispatch for message side effects failed (%s); running inline.",
                            exc,
                        )
                        try:
                            from communications.tasks import post_message_side_effects_task

                            post_message_side_effects_task.apply(
                                args=[
                                    message.id,
                                    other_participant.id,
                                    sender_name,
                                    content_preview,
                                    conversation.id,
                                ]
                            )
                        except Exception as inner:
                            logger.error("Inline message side effects failed: %s", inner, exc_info=True)

                transaction.on_commit(queue_side_effects)

                return Response(message_payload, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to send message'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark all messages in conversation as read"""
        try:
            conversation = self.get_object()
            conversation.messages.filter(
                read_at__isnull=True
            ).exclude(sender=request.user).update(read_at=timezone.now())
            
            # Update Firestore records for these read messages
            firestore_service = get_firestore_service()
            if firestore_service:
                for msg in conversation.messages.filter(read_at__isnull=False).exclude(sender=request.user):
                    firestore_service.sync_message(msg)
            
            # Also mark related notifications as read
            Notification.objects.filter(
                user=request.user,
                related_object_id=conversation.id,
                is_read=False
            ).update(is_read=True)
            
            return Response({
                'status': 'success',
                'message': 'Conversation marked as read'
            })
        except Exception as e:
            logger.error(f"Error marking conversation as read: {e}")
            return Response(
                {'error': 'Failed to mark conversation as read'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def start_conversation(self, request):
        """Start a new conversation with another user"""
        try:
            # For phase 1: 'user_id' in body is the AGENT (or target user).
            # The requester is the CLIENT (or initiator).
            # However, looking at the requirements, 'user visits property page'.
            # Requester = User. Target = Agent.
            
            # Check payload
            logger.debug("start_conversation payload keys=%s", list(getattr(request, "data", {}) or {}))
            
            seller_id = request.data.get('seller_id') or request.data.get('agent_id') or request.data.get('user_id')
            listing_id = request.data.get('listing_id')
            order_id = request.data.get('order_id')
            dispute_id = request.data.get('dispute_id')
            
            # If listing_id is provided, we can get seller_id from listing owner
            if not seller_id and not listing_id:
                return Response(
                    {'error': 'seller_id (or user_id) or listing_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate IDs
            if seller_id:
                try:
                    seller_id = int(seller_id)
                except (ValueError, TypeError):
                    return Response({'error': 'Invalid seller_id format'}, status=status.HTTP_400_BAD_REQUEST)

            # Check for self-chat
            if seller_id == request.user.id:
                logger.warning(f"User {request.user.id} attempted to start a conversation with themselves.")
                return Response(
                    {'error': 'You cannot start a conversation with yourself. This appears to be your own listing.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            listing_obj = None
            if listing_id:
                try:
                    listing_obj = Listing.objects.get(id=listing_id)
                    # If seller_id wasn't provided, use listing owner
                    if not seller_id:
                        seller_id = listing_obj.owner.id
                except Listing.DoesNotExist:
                    return Response({'error': 'Listing not found'}, status=status.HTTP_404_NOT_FOUND)
            
            order_obj = None
            if order_id:
                try:
                    order_obj = Order.objects.get(id=order_id)
                    # If seller_id wasn't provided, determine from order
                    if not seller_id:
                        seller_id = order_obj.seller.id
                except Order.DoesNotExist:
                    return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
            
            dispute_obj = None
            if dispute_id:
                try:
                    dispute_obj = Dispute.objects.get(id=dispute_id)
                except Dispute.DoesNotExist:
                    return Response({'error': 'Dispute not found'}, status=status.HTTP_404_NOT_FOUND)
            
            # Now fetch seller_user if we have seller_id
            if seller_id:
                User = get_user_model()
                try:
                    seller_user = User.objects.get(id=seller_id)
                except User.DoesNotExist:
                    return Response({'error': 'Seller/User not found'}, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({'error': 'Could not determine seller_id'}, status=status.HTTP_400_BAD_REQUEST)

            # Check for existing conversation between these two users (CONSOLIDATION)
            conversation = Conversation.objects.filter(
                (Q(user=request.user) & Q(seller=seller_user)) |
                (Q(user=seller_user) & Q(seller=request.user))
            ).order_by('-updated_at').first()

            if conversation:
                # Update the context for the existing conversation if a new one is provided.
                update_fields = []
                if listing_obj and conversation.listing != listing_obj:
                    conversation.listing = listing_obj
                    update_fields.append('listing')
                if order_obj and conversation.order != order_obj:
                    conversation.order = order_obj
                    update_fields.append('order')
                if dispute_obj and conversation.dispute != dispute_obj:
                    conversation.dispute = dispute_obj
                    update_fields.append('dispute')
                
                if update_fields:
                    update_fields.append('updated_at')
                    conversation.save(update_fields=update_fields)
                
                conversation.hidden_by.clear()
                logger.info(f"Consolidation: Using existing conversation {conversation.id}")
            else:
                # Create a new conversation only if none exists
                conversation = Conversation.objects.create(
                    user=request.user,
                    seller=seller_user,
                    listing=listing_obj,
                    order=order_obj,
                    dispute=dispute_obj
                )
                logger.info(f"Created new conversation {conversation.id}")
                
                # Send notification for NEW conversation
                notification_service = get_notification_service()
                if notification_service:
                    # Get context title for notification
                    context_title = "New Inquiry"
                    if conversation.listing:
                        context_title = conversation.listing.title
                    elif conversation.order:
                        context_title = f"Order #{conversation.order.id}"
                    elif conversation.dispute:
                        context_title = f"Dispute #{conversation.dispute.id}"
                    
                # Send notification for NEW conversation asynchronously
                notify_new_conversation_task.delay(
                    user_id=seller_user.id,
                    context_title=context_title,
                    participant_name=request.user.get_full_name() or request.user.username,
                    conversation_id=conversation.id,
                    channels=['email', 'push']
                )
                
                # Sync new conversation to Firestore Sidecar
                firestore_service = get_firestore_service()
                if firestore_service:
                    firestore_service.sync_conversation(conversation)
            
            
            return Response(
                ConversationSerializer(
                    conversation,
                    context={'request': request}
                ).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.error(f"Error starting conversation: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to start conversation'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['patch', 'put'])
    def update_listing(self, request, pk=None):
        """Update the listing associated with a conversation"""
        try:
            conversation = self.get_object()
            if conversation.user != request.user and conversation.seller != request.user:
                return Response(
                    {'error': 'You do not have permission to update this conversation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            listing_id = request.data.get('listing_id')
            
            if listing_id is None:
                conversation.listing = None
                conversation.save()
                return Response(
                    ConversationSerializer(conversation, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )
            
            try:
                listing_obj = Listing.objects.get(id=listing_id)
                conversation.listing = listing_obj
                conversation.save()
                
                return Response(
                    ConversationSerializer(conversation, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )
            except Listing.DoesNotExist:
                return Response(
                    {'error': 'Listing not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Exception as e:
            logger.error(f"Error updating conversation listing: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to update conversation listing'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active conversations"""
        try:
            conversations = self.get_queryset().filter(is_active=True)
            serializer = self.get_serializer(conversations, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error fetching active conversations: {e}")
            return Response(
                {'error': 'Failed to fetch active conversations'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(responses={200: inline_serializer("UnreadCountResponse", fields={"unread_count": serializers.IntegerField()})})
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get total unread message count for the user"""
        try:
            user = request.user
            count = Message.objects.filter(
                Q(conversation__user=user) | Q(conversation__seller=user),
                read_at__isnull=True
            ).exclude(sender=user).count()
            return Response({'unread_count': count})
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return Response(
                {'error': 'Failed to get unread count'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    @action(detail=True, methods=['post'])
    def clear_history(self, request, pk=None):
        """Clear conversation history for the current user"""
        try:
            conversation = self.get_object()
            if not self._is_participant(request.user, conversation):
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            
            # Get all messages visible to user (not yet hidden)
            # We want to add user to hidden_by of ALL messages in conversation
            # Using bulk create for M2M is tricky because it's a through table implicit model usually, 
            # but standard .add() on queryset is not supported directly for many-to-many reverse
            
            # Efficient way: 
            # messages = conversation.messages.exclude(hidden_by=request.user)
            # for msg in messages: msg.hidden_by.add(request.user) -> Slow loop
            
            # Correct Bulk way:
            messages = conversation.messages.exclude(hidden_by=request.user)
            
            # We can use the through model directly
            MessageHiddenBy = Message.hidden_by.through
            new_relations = []
            for msg in messages:
                new_relations.append(MessageHiddenBy(message_id=msg.id, user_id=request.user.id))
            
            MessageHiddenBy.objects.bulk_create(new_relations, ignore_conflicts=True)
            
            # 2. Hide the conversation itself from the list
            conversation.hidden_by.add(request.user)
            
            return Response({'status': 'Conversation history cleared and hidden'})
        except Exception as e:
            logger.error(f"Error clearing history: {e}")
            return Response(
                {'error': 'Failed to clear history'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def destroy(self, request, *args, **kwargs):
        """Standard DELETE method hides conversation for current user"""
        return self.clear_history(request, *args, **kwargs)


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['conversation']
    ordering_fields = ['created_at']
    ordering = ['created_at']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Message.objects.none()
        return super().get_queryset()
    # pagination_class = None # Remove this line to enable default pagination (PageNumberPagination) OR set it explicitly
    # Using default PageNumberPagination from settings

    http_method_names = ['get', 'post', 'delete', 'head', 'options']


    def create(self, request, *args, **kwargs):
        """Create a new message"""
        try:
            conversation_id = request.data.get('conversation')
            if not conversation_id:
                return Response({'error': 'conversation field is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                conversation = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)

            # Check permissions
            if request.user != conversation.user and request.user != conversation.seller:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            serializer = CreateMessageSerializer(
                data=request.data,
                context={'conversation': conversation, 'request': request}
            )

            if serializer.is_valid():
                message = serializer.save()
                
                # Unhide conversation for both participants
                conversation.hidden_by.clear()

                # Send external notifications (Email/Push)
                # Note: DB notifications are handled by custom logic in views/serializers usually,
                # but CreateMessageSerializer puts basic MessageNotification.
                
                notification_service = get_notification_service()
                
                other_participant = conversation.seller if conversation.user == request.user else conversation.user
                
                content_preview = message.text[:100] if message.text else "Attachment"
                
                # Send external notifications (Email/Push) asynchronously
                post_message_side_effects_task.delay(
                    message.id,
                    other_participant.id,
                    request.user.get_full_name() or request.user.username,
                    content_preview,
                    conversation.id
                )

                # Broadcast to WebSocket group
                try:
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f'chat_{conversation.id}',
                        {
                            'type': 'chat.message',
                            'message': MessageSerializer(message).data,
                            'sender_id': request.user.id,
                        }
                    )
                except Exception as ws_error:
                    logger.error(f"WebSocket broadcast failed: {ws_error}")

                # Sync real-time message to Firestore Sidecar
                firestore_service = get_firestore_service()
                if firestore_service:
                    firestore_service.sync_message(message)

                return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            return Response({'error': 'Failed to create message'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'])
    def delete_for_everyone(self, request, pk=None):
        """Delete a message for everyone (within time window)"""
        try:
            message = self.get_object()
            
            # Only sender can delete
            if message.sender != request.user:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            
            # Check time window (e.g., 1 hour)
            time_diff = timezone.now() - message.created_at
            if time_diff.total_seconds() > 3600:
                return Response({'error': 'Message too old to delete for everyone'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Soft delete globally
            message.is_deleted = True
            message.text = "This message was deleted" # Optional: update DB text too, but serializer handles it.
            # We should probably clear connection to file to save space or just keep it?
            # Req: "Remove attachments"
            message.attachment = None
            message.deleted_at = timezone.now()
            message.save()
            
            # Broadcast deletion
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'chat_{message.conversation.id}',
                    {
                        'type': 'chat.message',
                        'message': MessageSerializer(message).data,
                        'sender_id': request.user.id,
                    }
                )
            except Exception as e:
                logger.error(f"Error broadcasting deletion: {e}")
                
            # Update Firestore deletion status
            firestore_service = get_firestore_service()
            if firestore_service:
                firestore_service.delete_message(message.conversation.id, message.id)
                
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Message.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
             logger.error(f"Error deleting message: {e}")
             return Response({'error': 'Failed to delete message'}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """Intelligent DELETE - try for everyone, fallback to for me"""
        try:
            message = self.get_object()
            
            # Check if we can delete for everyone
            can_delete_for_everyone = (
                message.sender == request.user and 
                (timezone.now() - message.created_at).total_seconds() <= 3600
            )
            
            if can_delete_for_everyone:
                return self.delete_for_everyone(request, pk=message.id)
            else:
                return self.delete_for_me(request, pk=message.id)
        except Message.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error in destroy: {e}")
            return Response({'error': 'Failed to delete message'}, status=status.HTTP_400_BAD_REQUEST)
    
    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(
            Q(conversation__user=user) | Q(conversation__seller=user)
        ).select_related('sender', 'conversation')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a message as read"""
        try:
            message = self.get_object()
            
            is_participant = (request.user == message.conversation.user) or (request.user == message.conversation.seller)
            
            if not is_participant:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if not message.read_at:
                message.read_at = timezone.now()
                message.save()
            
            return Response({'status': 'Message marked as read'})
        except Exception as e:
            logger.error(f"Error marking message as read: {e}")
            return Response(
                {'error': 'Failed to mark message as read'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['delete'])
    def delete_for_me(self, request, pk=None):
        """Hidden a message for the current user only"""
        try:
            message = self.get_object()
            
            # Check if participant
            is_participant = (request.user == message.conversation.user) or (request.user == message.conversation.seller)
            if not is_participant:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            
            message.hidden_by.add(request.user)
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Message.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error deleting message for me: {e}")
            return Response({'error': 'Failed to delete message'}, status=status.HTTP_400_BAD_REQUEST)


# Views from notifications app
class NotificationViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows notifications to be viewed or edited.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    
    @extend_schema(operation_id="api_v1_communications_notifications_list_alt")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        """
        This view should return a list of all the notifications
        for the currently authenticated user.
        """
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    def destroy(self, request, *args, **kwargs):
        """Delete a notification - only if it belongs to the current user"""
        try:
            # get_object() already filters by get_queryset() which filters by user
            notification = self.get_object()
            notification.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Notification.DoesNotExist:
            logger.warning(f"Notification not found or already deleted: {kwargs.get('pk')}")
            # Return 204 (success) even if already deleted - idempotent delete
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error deleting notification: {e}")
            return Response(
                {'error': 'Failed to delete notification'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a single notification as read"""
        try:
            notification = self.get_object()
            notification.is_read = True
            notification.save()
            return Response({'status': 'Notification marked as read'})
        except Notification.DoesNotExist:
            return Response({'error': 'Notification not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


    @extend_schema(operation_id="api_v1_communications_notifications_mark_all_read")
    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """Mark all notifications as read for the current user"""
        try:
            self.get_queryset().filter(is_read=False).update(is_read=True)
            return Response({'status': 'All notifications marked as read'})
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        operation_id="api_v1_communications_notifications_unread_count",
        responses={200: inline_serializer("NotificationUnreadCountResponse", fields={"unread_count": serializers.IntegerField()})}
    )
    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """Get count of unread notifications for the current user"""
        try:
            count = self.get_queryset().filter(is_read=False).count()
            return Response({'unread_count': count})
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SupportRequestViewSet(viewsets.ModelViewSet):
    serializer_class = SupportRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['subject', 'message']
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SupportRequest.objects.none()
        user = self.request.user
        if user.is_staff:
            return SupportRequest.objects.all()
        return SupportRequest.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)




class DeviceTokenViewSet(viewsets.ModelViewSet):
    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['post', 'delete']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return DeviceToken.objects.none()
        return DeviceToken.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """Register a new device token"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['delete'])
    def clear(self, request):
        """Clear the current token"""
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        DeviceToken.objects.filter(user=request.user, token=token).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
