import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=60)
def send_welcome_email(self, user_id):
    """Sends a welcome email when a new user registers."""
    try:
        user = User.objects.get(id=user_id)
        subject = "Welcome to SmartDalali!"
        message = f"Hi {user.username},\n\nWelcome to SmartDalali! We are excited to have you on our platform."
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        logger.info(f"Welcome email sent to user {user_id}")
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for welcome email")
    except Exception as exc:
        logger.error(f"Error sending welcome email to {user_id}: {exc}")
        raise

@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=60)
def send_activation_email_task(self, user_id):
    """Task version of account activation email."""
    try:
        user = User.objects.get(id=user_id)
        from core.services.accounts import AccountService
        AccountService.send_activation_email(user)
        logger.info(f"Activation email task completed for user {user_id}")
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for activation email task")
    except Exception as exc:
        logger.error(f"Error in send_activation_email_task for {user_id}: {exc}")
        raise

@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=60)
def send_password_reset_email_task(self, user_id, reset_link):
    """Sends a password reset email asynchronously."""
    try:
        user = User.objects.get(id=user_id)
        subject = "Password Reset Request"
        message = f"Click the link below to reset your password:\n{reset_link}\n\nIf you didn't request this, please ignore this email."
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        logger.info(f"Password reset email sent to user {user_id}")
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for password reset email")
    except Exception as exc:
        logger.error(f"Error sending password reset email to {user_id}: {exc}")
        raise
