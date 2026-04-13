from core.services.notifications import (
    BaseNotificationService,
    logger
)
from typing import Optional, List

class NotificationService(BaseNotificationService):
    """Unified notification service (Legacy implementation)"""
    
    def notify_new_message(
        self, 
        user, 
        sender_name: str, 
        message_preview: str,
        conversation_id: int = None,
        channels: Optional[List[str]] = None
    ):
        """
        Send notification through multiple channels
        channels: ['email', 'sms', 'push']
        """
        if channels is None:
            channels = ['email', 'push']
            
        # 1. Create DB Notification
        self.create_db_notification(
            user=user,
            type='message',
            title=f"New Message from {sender_name}",
            message=message_preview,
            data={'sender_name': sender_name},
            related_object_id=conversation_id,
            related_object_type='conversation'
        )

        # 3. Send External Notifications
        try:
            if 'email' in channels and user.email:
                self.email.send_message_notification(
                    user.email, sender_name, message_preview
                )
            
            if 'sms' in channels and hasattr(user, 'profile') and user.profile.phone_number:
                self.sms.send_message_alert(
                    user.profile.phone_number, sender_name, message_preview
                )
            
            if 'push' in channels:
                self.push.send_message_notification(
                    user, sender_name, message_preview
                )
        except Exception as e:
            logger.error(f"Error sending external notifications: {e}")
    
    def notify_new_conversation(
        self,
        user,
        property_title: str,
        participant_name: str,
        conversation_id: int = None,
        channels: Optional[List[str]] = None
    ):
        """Send notification for new conversation"""
        if channels is None:
            channels = ['email', 'push']
            
        # 1. Create DB Notification
        self.create_db_notification(
            user=user,
            type='message',
            title=f"New Inquiry: {property_title}",
            message=f"{participant_name} started a new conversation about {property_title}",
            data={'property_title': property_title, 'participant_name': participant_name},
            related_object_id=conversation_id,
            related_object_type='conversation'
        )
        
        try:
            if 'email' in channels and user.email:
                self.email.send_conversation_alert(
                    user.email, property_title, participant_name
                )
            
            if 'sms' in channels and hasattr(user, 'profile') and user.profile.phone_number:
                self.sms.send_conversation_alert(
                    user.profile.phone_number, property_title
                )
            
            if 'push' in channels:
                self.push.send_conversation_notification(
                    user, property_title, participant_name
                )
        except Exception as e:
            logger.error(f"Error sending conversation notifications: {e}")
            
    def notify_generic(
        self,
        user,
        title: str,
        message: str,
        notification_type: str = 'update',
        related_object_id: int = None,
        related_object_type: str = None,
        send_push: bool = True,
        extra_data: dict | None = None,
    ):
        """Send a generic notification"""
        try:
            payload = dict(extra_data or {})
            db_notification = self.create_db_notification(
                user=user,
                type=notification_type,
                title=title,
                message=message,
                data=payload,
                related_object_id=related_object_id,
                related_object_type=related_object_type
            )
                
            # 3. Handle Push if requested
            if send_push:
                push_data = {
                    'type': notification_type,
                    'related_id': str(related_object_id) if related_object_id else '',
                    **{k: str(v) for k, v in payload.items()},
                }
                self.push.send_to_user(user, title, message, data=push_data)

            return db_notification
            
        except Exception as e:
            logger.error(f"Error sending generic notification: {e}")
            return None


# Singleton instance
_notification_service = None


def get_notification_service():
    """Get the notification service instance"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
