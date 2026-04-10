import logging
import threading
from typing import Optional, Tuple, Dict, Any
from django.contrib.auth.models import User, Group
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import Profile
from accounts.otp import send_otp
from accounts.tasks import send_welcome_email
from django.core.mail import send_mail
from django.template.loader import render_to_string
from marketplace.models import SellerProfile

logger = logging.getLogger(__name__)


class AccountService:
    @staticmethod
    def resolve_user_by_email(email: str) -> Optional[User]:
        """Resolve a user by their email address (case-insensitive)."""
        if not email:
            return None
        User = get_user_model()
        return User.objects.filter(email__iexact=email.strip()).first()

    @staticmethod
    @transaction.atomic
    def register_user(validated_data: Dict[str, Any]) -> User:
        """Handle user registration. Optional ``role``: buyer (default), seller, or both add seller group."""
        validated_data.pop('is_agent', None)
        validated_data.pop('is_seller', None)
        role = (validated_data.pop('role', None) or 'buyer').strip().lower()
        if role not in ('buyer', 'seller', 'both'):
            role = 'buyer'
        phone_number = validated_data.pop('phone_number', None)

        User = get_user_model()
        # Create user
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )

        # User remains inactive until OTP verification
        user.is_active = False
        user.save()

        # Profile is usually created by signal. Ensure it exists and update phone.
        profile, _ = Profile.objects.get_or_create(user=user)
        if phone_number:
            profile.phone_number = phone_number
        profile.save()

        # Send OTP for email verification using the new OTP system
        try:
            send_otp(user, purpose='verify_email')
            
            # Send welcome email as well
            send_welcome_email.delay(user.id)
        except Exception as e:
            logger.error(f"Failed to send verification OTP for {user.username}: {str(e)}")

        if role in ('seller', 'both'):
            AccountService.toggle_seller_role(user)

        return user

    @staticmethod
    def send_activation_email(user: User):
        """Send activation email to the user."""
        if not user.email:
            return

        try:
            profile = user.profile
            frontend = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
            activation_link = f"{frontend}/activate?username={user.username}&code={profile.code}"

            subject = 'Activate Your SmartDalali Account'
            context = {
                'username': user.username,
                'activation_link': activation_link,
            }

            text_body = render_to_string('emails/activation_email.txt', context)
            html_body = render_to_string('emails/activation_email.html', context)

            send_mail(
                subject,
                text_body,
                settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
                [user.email],
                html_message=html_body,
                fail_silently=True,
            )
            logger.info(f"Activation email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send activation email for {user.username}: {str(e)}")

    @staticmethod
    @transaction.atomic
    def update_profile(user: User, data: Dict[str, Any], files: Optional[Dict[str, Any]] = None) -> User:
        """Orchestrate profile updates across User and Profile models."""

        # Helper to handle nested 'user', 'profile' keys or flat data
        def get_val(key, nested_key=None):
            if nested_key and isinstance(data.get(key), dict):
                return data[key].get(nested_key)
            return data.get(nested_key or key)

        # 1. Update User model
        user_changed = False
        for field in ('first_name', 'last_name', 'email'):
            val = get_val('user', field)
            if val is not None and getattr(user, field) != val:
                setattr(user, field, val)
                user_changed = True

        if user_changed:
            user.save()

        # 2. Update Profile model
        profile, _ = Profile.objects.get_or_create(user=user)
        profile_changed = False

        name = get_val('profile', 'name') or data.get('profile_name') or data.get('name')
        phone = get_val('profile', 'phone_number') or data.get('phone_number') or data.get('phone')
        address = get_val('profile', 'address') or data.get('address')

        if name is not None and profile.name != name:
            profile.name = name
            profile_changed = True
        if phone is not None and profile.phone_number != phone:
            profile.phone_number = phone
            profile_changed = True
        if address is not None and profile.address != address:
            profile.address = address
            profile_changed = True

        # Handle image upload
        if files:
            image_file = (
                files.get('profile.image')
                or files.get('profile_image')
                or files.get('image')
                or files.get('profile_picture')
            )
            if image_file:
                profile.image = image_file
                profile_changed = True

        if profile_changed:
            profile.save()

        return user

    @staticmethod
    @transaction.atomic
    def firebase_authenticate(firebase_data: Dict[str, Any]) -> Tuple[User, bool]:
        """Handle Firebase authentication and user syncing."""
        email = firebase_data.get('email')
        firebase_uid = firebase_data.get('firebase_uid')
        display_name = firebase_data.get('display_name')
        phone_number = firebase_data.get('phone_number')

        User = get_user_model()
        user = User.objects.filter(email=email).first()
        created = False

        if not user:
            # Create new user
            username = email.split('@')[0] if email else f'firebase_{firebase_uid[:10]}'
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f'{base_username}_{counter}'
                counter += 1

            user = User.objects.create(
                email=email,
                username=username,
                first_name=display_name or '',
                is_active=True
            )
            created = True
        elif display_name and not user.first_name:
            user.first_name = display_name
            user.save()

        # Sync Profile
        profile, _ = Profile.objects.get_or_create(user=user)
        profile_changed = False

        if display_name and not profile.name:
            profile.name = display_name
            profile_changed = True

        if not profile.firebase_uid:
            profile.firebase_uid = firebase_uid
            profile_changed = True

        if phone_number and not profile.phone_number:
            profile.phone_number = phone_number
            profile_changed = True

        if profile_changed:
            profile.save()

        return user, created

    @staticmethod
    @transaction.atomic
    def toggle_seller_role(user: User) -> Tuple[bool, str]:
        """Upgrade a user to a marketplace Seller."""

        seller_group, _ = Group.objects.get_or_create(name='seller')
        is_now_seller = False

        if user.groups.filter(name='seller').exists():
            # If they already have the group, make sure they have a SellerProfile
            SellerProfile.objects.get_or_create(user=user)
            message = f"{user.username} is already a seller"
            is_now_seller = True
        else:
            user.groups.add(seller_group)
            Profile.objects.get_or_create(user=user)
            SellerProfile.objects.get_or_create(user=user)
            message = f"{user.username} is now a seller"
            is_now_seller = True

        return is_now_seller, message

    @staticmethod
    @transaction.atomic
    def downgrade_from_seller(user: User) -> Tuple[bool, str]:
        """Remove seller role from a user."""

        seller_group = Group.objects.filter(name='seller').first()
        if seller_group:
            user.groups.remove(seller_group)

        # Deactivate seller profile if exists
        try:
            seller_profile = user.seller_profile
            seller_profile.is_active = False
            seller_profile.save()
        except Exception:
            pass

        return False, f"{user.username} is no longer a seller"
