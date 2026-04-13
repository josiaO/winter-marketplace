"""
Notification services using third-party providers
Moved to core to be accessible by all modules.
"""
import logging
from typing import Optional, List
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

# External Integrations
try:
    from twilio.rest import Client as TwilioClient
except ImportError:
    TwilioClient = None

try:
    import firebase_admin
    from firebase_admin import messaging as firebase_messaging
except ImportError:
    firebase_admin = None
    firebase_messaging = None

# Internal App Imports
from communications.models import DeviceToken, Notification
from communications.serializers import NotificationSerializer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """Send emails using SendGrid"""
    
    @staticmethod
    def send_message_notification(recipient_email: str, sender_name: str, message_preview: str):
        """Send email notification for new message"""
        try:
            subject = f"New message from {sender_name}"
            html_message = render_to_string('notifications/new_message.html', {
                'sender_name': sender_name,
                'message_preview': message_preview,
                'action_url': f"{settings.FRONTEND_URL}/messages"
            })
            
            send_mail(
                subject,
                f"New message from {sender_name}: {message_preview}",
                settings.DEFAULT_FROM_EMAIL,
                [recipient_email],
                html_message=html_message,
                fail_silently=True,
            )
            logger.info(f"Email notification sent to {recipient_email}")
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
    
    @staticmethod
    def send_conversation_alert(recipient_email: str, property_title: str, participant_name: str):
        """Send email alert for new conversation"""
        try:
            subject = f"New inquiry about {property_title}"
            html_message = render_to_string('notifications/new_conversation.html', {
                'property_title': property_title,
                'participant_name': participant_name,
                'action_url': f"{settings.FRONTEND_URL}/messages"
            })
            
            send_mail(
                subject,
                f"New inquiry about {property_title} from {participant_name}",
                settings.DEFAULT_FROM_EMAIL,
                [recipient_email],
                html_message=html_message,
                fail_silently=True,
            )
            logger.info(f"Conversation alert sent to {recipient_email}")
        except Exception as e:
            logger.error(f"Failed to send conversation alert: {e}")


class SMSNotificationService:
    """Send SMS using Twilio"""
    
    def __init__(self):
        try:
            if TwilioClient:
                self.client = TwilioClient(
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN
                )
                self.from_number = settings.TWILIO_PHONE_NUMBER
            else:
                self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Twilio: {e}")
            self.client = None
    
    def send_message_alert(self, phone_number: str, sender_name: str, message_preview: str):
        """Send SMS alert for new message"""
        if not self.client:
            logger.warning("Twilio not configured")
            return
        
        try:
            message_body = f"New message from {sender_name}: {message_preview[:50]}..."
            self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=phone_number
            )
            logger.info(f"SMS sent to {phone_number}")
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
    
    def send_conversation_alert(self, phone_number: str, property_title: str):
        """Send SMS alert for new conversation"""
        if not self.client:
            logger.warning("Twilio not configured")
            return
        
        try:
            message_body = f"New inquiry about {property_title}. Check DigitalDalali app for details."
            self.client.messages.create(
                body=message_body,
                from_=self.from_number,
                to=phone_number
            )
            logger.info(f"Conversation SMS sent to {phone_number}")
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")


class PushNotificationService:
    """Send push notifications using Firebase"""
    
    def __init__(self):
        try:
            self.messaging = firebase_messaging
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            self.messaging = None
    
    def send_push(self, user, title, body, data=None):
        """Send push notification to all devices of a user"""
        if not self.messaging:
            logger.warning("Firebase not configured")
            return False
        tokens = DeviceToken.objects.filter(user=user).values_list('token', flat=True)
        if not tokens:
            logger.info(f"No device tokens found for user {user.username}")
            return False

        success_count = 0
        tokens_to_delete = []
        
        safe_data = {str(k): str(v) for k, v in (data or {}).items() if v is not None}

        for token in tokens:
            try:
                msg = self.messaging.Message(
                    notification=self.messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data=safe_data,
                    token=token,
                )
                self.messaging.send(msg)
                success_count += 1
            except Exception as e:
                # Check for invalid token errors
                error_code = getattr(e, 'code', None)
                error_str = str(e)
                invalid_codes = [
                    'registration-token-not-registered', 
                    'invalid-registration-token', 
                    'message-rate-exceeded',
                    'messaging/registration-token-not-registered',
                    'messaging/invalid-registration-token'
                ]
                
                if (error_code in invalid_codes) or ('NotRegistered' in error_str) or ('InvalidRegistration' in error_str) or ('Requested entity was not found' in error_str):
                    tokens_to_delete.append(token)
                logger.warning(f"Failed to send push to token {token[:10]}...: {e}")

        if success_count > 0:
            logger.info(f"Successfully sent {success_count} push notifications for {user.username}")

        # Clean up invalid tokens
        if tokens_to_delete:
            DeviceToken.objects.filter(token__in=tokens_to_delete).delete()
            logger.info(f"Cleaned up {len(tokens_to_delete)} invalid device tokens")
            
        return success_count > 0

    def send_message_notification(self, user, sender_name: str, message_preview: str):
        """Send push notification for new message"""
        return self.send_push(
            user, 
            f"Message from {sender_name}", 
            message_preview[:100],
            data={'type': 'message'}
        )
    
    def send_conversation_notification(self, user, property_title: str, participant_name: str):
        """Send push notification for new conversation"""
        return self.send_push(
            user,
            "New inquiry",
            f"{participant_name} inquired about {property_title}",
            data={'type': 'conversation', 'property_title': property_title}
        )

    def send_to_user(self, user, title, body, data=None):
        """Alias for send_push for backwards compatibility"""
        return self.send_push(user, title, body, data)


class BaseNotificationService:
    """Unified notification service base class"""
    
    def __init__(self):
        self.email = EmailNotificationService()
        self.sms = SMSNotificationService()
        self.push = PushNotificationService()

    def create_db_notification(self, user, type, title, message, data=None, related_object_id=None, related_object_type=None):
        """Create a notification in the database"""
        try:
            db_notification = Notification.objects.create(
                user=user,
                type=type,
                title=title,
                message=message,
                data=data or {},
                related_object_id=related_object_id,
                related_object_type=related_object_type
            )
            
            # Broadcast to WebSocket
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"notifications_{user.id}",
                    {
                        "type": "notification",
                        "message": NotificationSerializer(db_notification).data
                    }
                )
            return db_notification
        except Exception as e:
            logger.error(f"Error creating DB notification: {e}")
            return None
