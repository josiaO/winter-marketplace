import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from communications.notification_service import get_notification_service
from communications.firestore_service import get_firestore_service

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=0)
def post_message_side_effects_task(
    self,
    message_id: int,
    recipient_user_id: int,
    sender_name: str,
    preview: str,
    conversation_id: int,
):
    """
    Email/push + DB notification + Firestore sync after a chat message is saved.
    Runs out-of-band so the HTTP POST returns quickly. No Celery retries (avoid duplicate emails).
    """
    from communications.models import Message

    try:
        message = Message.objects.select_related('sender', 'conversation').get(pk=message_id)
    except Message.DoesNotExist:
        logger.warning("post_message_side_effects_task: message %s missing", message_id)
        return

    try:
        recipient = User.objects.get(pk=recipient_user_id)
    except User.DoesNotExist:
        logger.warning("post_message_side_effects_task: user %s missing", recipient_user_id)
        return

    notification_service = get_notification_service()
    if notification_service:
        try:
            notification_service.notify_new_message(
                recipient,
                sender_name,
                preview or "New message",
                conversation_id=conversation_id,
                channels=['push', 'email'],
            )
        except Exception as exc:
            logger.error("notify_new_message failed: %s", exc, exc_info=True)

    firestore_service = get_firestore_service()
    if firestore_service:
        try:
            firestore_service.sync_message(message)
        except Exception as exc:
            logger.error("Firestore sync_message failed: %s", exc, exc_info=True)

@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def send_generic_notification_task(self, user_id, title, message, notification_type='update', related_object_id=None, related_object_type=None, send_push=True):
    """
    Asynchronous task for sending generic notifications.
    This offloads the DB creation and Firebase push API calls from Django views.
    """
    try:
        user = User.objects.get(id=user_id)
        notification_service = get_notification_service()
        notification_service.notify_generic(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            related_object_id=related_object_id,
            related_object_type=related_object_type,
            send_push=send_push
        )
        logger.info(f"Successfully sent generic notification to user {user_id}")
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for notification.")
    except Exception as exc:
        logger.error(f"Failed to send generic notification for user {user_id}: {exc}")
        raise exc

@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def notify_new_conversation_task(self, user_id, context_title, participant_name, conversation_id=None, channels=None):
    """
    Asynchronous task for sending new conversation notifications.
    """
    try:
        user = User.objects.get(id=user_id)
        notification_service = get_notification_service()
        notification_service.notify_new_conversation(
            user,
            context_title,
            participant_name,
            conversation_id=conversation_id,
            channels=channels
        )
        logger.info(f"Successfully sent new conversation notification to user {user_id}")
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for NEW conversation notification.")
    except Exception as exc:
        logger.error(f"Failed to send NEW conversation notification for user {user_id}: {exc}")
        raise exc
