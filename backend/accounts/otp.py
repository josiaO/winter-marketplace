"""
OTP (One-Time Password) Service for SmartDalali
Handles generation, storage, verification, and email delivery of OTPs.
Used for:
  - Registration email confirmation
  - Password change confirmation
  - Sensitive action confirmation (e.g., large withdrawals)
"""
import secrets
import string
import logging
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from celery import shared_task
from .models import OTP

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = getattr(settings, 'OTP_EXPIRY_MINUTES', 10)
OTP_MAX_ATTEMPTS = getattr(settings, 'OTP_MAX_ATTEMPTS', 5)
OTP_LENGTH = getattr(settings, 'OTP_LENGTH', 6)


def generate_otp_code(length: int = OTP_LENGTH) -> str:
    """Generate a secure numeric OTP of the given length."""
    return ''.join(secrets.choice(string.digits) for _ in range(length))


def send_otp(user, purpose: str = 'verify_email', channel: str = 'email') -> 'OTP':
    """
    Generate and send an OTP to the user via chosen channel.
    Invalidates any previously active OTPs for the same purpose.
    
    Args:
        user: Django User instance
        purpose: One of 'verify_email', 'password_reset', 'confirm_action'
        channel: 'email' or 'sms'
    
    Returns:
        The newly created OTP instance
    """
    # Invalidate any prior active OTPs for this user+purpose
    OTP.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)

    code = generate_otp_code()
    expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    
    otp = OTP.objects.create(
        user=user,
        code=code,
        purpose=purpose,
        expires_at=expires_at,
    )

    # Trigger delivery task asynchronously
    send_otp_delivery_task.delay(user.id, code, purpose, channel)
        
    logger.info(f"OTP generated for user {user.email} (ID: {user.id}) for purpose '{purpose}'. Delivery task enqueued via {channel}.")
    return otp


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=60)
def send_otp_delivery_task(self, user_id, code, purpose, channel):
    """
    Celery task to deliver OTP via Email or SMS.
    Separates heavy delivery logic from the request-response cycle.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        user = User.objects.get(pk=user_id)
        
        if channel == 'sms':
            _send_otp_sms(user, code, purpose)
        else:
            _send_otp_email(user, code, purpose)
            
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for OTP delivery task")
    except Exception as exc:
        logger.error(f"Error in send_otp_delivery_task for user {user_id}: {exc}")
        raise


def verify_otp(user, code: str, purpose: str = 'verify_email') -> tuple[bool, str]:
    """
    Verify the OTP code provided by the user.
    
    Returns:
        A tuple (success: bool, message: str)
    """
    try:
        otp = OTP.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False,
        ).latest('created_at')
    except OTP.DoesNotExist:
        return False, "No active OTP found. Please request a new code."

    # Check expiry
    if timezone.now() > otp.expires_at:
        otp.is_used = True
        otp.save()
        return False, "OTP has expired. Please request a new code."

    # Check attempts
    if otp.attempts >= OTP_MAX_ATTEMPTS:
        otp.is_used = True
        otp.save()
        return False, "Too many failed attempts. Please request a new code."

    # Verify the code
    if otp.code != code.strip():
        otp.attempts += 1
        otp.save()
        remaining = OTP_MAX_ATTEMPTS - otp.attempts
        return False, f"Invalid OTP. {remaining} attempt(s) remaining."

    # Mark as used
    otp.is_used = True
    otp.save()

    # If it's email verification, mark the user's email as verified
    if purpose == 'verify_email':
        user.is_active = True
        user.save(update_fields=['is_active'])
        try:
            profile = user.profile
            profile.email_verified = True
            profile.save(update_fields=['email_verified'])
        except Exception as e:
            logger.warning(f"Could not update email_verified for user {user.id}: {e}")

    return True, "OTP verified successfully."


def _send_otp_email(user, code: str, purpose: str):
    """Helper to send the OTP via email."""
    subject_map = {
        'verify_email': 'Verify Your SmartDalali Account',
        'password_reset': 'Password Reset Code — SmartDalali',
        'confirm_action': 'Confirm Your Action — SmartDalali',
        'delete_account': 'CRITICAL: Account Deletion Code — SmartDalali',
    }
    body_map = {
        'verify_email': (
            f"Hi {user.first_name or user.username},\n\n"
            f"Your SmartDalali email verification code is:\n\n"
            f"  {code}\n\n"
            f"This code expires in {OTP_EXPIRY_MINUTES} minutes.\n\n"
            "If you didn't request this, please ignore this email.\n\n"
            "— The SmartDalali Team"
        ),
        'password_reset': (
            f"Hi {user.first_name or user.username},\n\n"
            f"Your password reset OTP is:\n\n"
            f"  {code}\n\n"
            f"This code expires in {OTP_EXPIRY_MINUTES} minutes.\n\n"
            "If you didn't request a password reset, please ignore this email.\n\n"
            "— The SmartDalali Team"
        ),
        'confirm_action': (
            f"Hi {user.first_name or user.username},\n\n"
            f"Your confirmation OTP is:\n\n"
            f"  {code}\n\n"
            f"This code expires in {OTP_EXPIRY_MINUTES} minutes.\n\n"
            "If you didn't request this, please ignore this email.\n\n"
            "— The SmartDalali Team"
        ),
        'delete_account': (
            f"Hi {user.first_name or user.username},\n\n"
            f"You have requested to PERMANENTLY DELETE your SmartDalali account.\n\n"
            f"YOUR DELETION CODE IS:\n\n"
            f"  {code}\n\n"
            f"This code expires in {OTP_EXPIRY_MINUTES} minutes.\n\n"
            "WARNING: If you enter this code, your account and all associated data will be deactivated. "
            "If you did not request this, please change your password immediately and contact support.\n\n"
            "— The SmartDalali Team"
        ),
    }
    
    subject = subject_map.get(purpose, 'Your OTP Code — SmartDalali')
    body = body_map.get(purpose, f"Your OTP is: {code}\n\nExpires in {OTP_EXPIRY_MINUTES} minutes.")
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@smartdalali.com')

    try:
        send_mail(subject, body, from_email, [user.email], fail_silently=False)
    except Exception as e:
        logger.error(f"Failed to send OTP email to {user.email}: {e}")


def _send_otp_sms(user, code: str, purpose: str):
    """Helper to send the OTP via SMS using Twilio."""
    from core.services.notifications import SMSNotificationService
    
    # Simple message template
    templates = {
        'verify_email': f"Your SmartDalali verification code is: {code}. Valid for {OTP_EXPIRY_MINUTES} mins.",
        'password_reset': f"SmartDalali Password Reset: {code}. Valid for {OTP_EXPIRY_MINUTES} mins.",
        'confirm_action': f"SmartDalali Confirmation Code: {code}.",
        'delete_account': f"CRITICAL: Account Deletion Code: {code}. PERMANENT ACTION.",
    }
    
    body = templates.get(purpose, f"Your SmartDalali OTP is: {code}")
    phone = getattr(user, 'profile', None).phone_number if hasattr(user, 'profile') else None
    
    if not phone:
        logger.error(f"Cannot send SMS OTP: User {user.username} has no phone number.")
        return

    try:
        sms_service = SMSNotificationService()
        # Twilio client handles the actual sending
        if sms_service.client:
            sms_service.client.messages.create(
                body=body,
                from_=sms_service.from_number,
                to=phone
            )
            logger.info(f"OTP SMS sent to {phone} for user {user.username}")
        else:
            # Fallback to console for dev mimicking production
            print(f"\n[DEVELOPMENT SMS MIMIC]\nTo: {phone}\nBody: {body}\n")
    except Exception as e:
        logger.error(f"Failed to send OTP SMS to {phone}: {e}")
