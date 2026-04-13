from datetime import datetime, timezone

from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserAddress, Profile
from .roles import get_user_role

from drf_spectacular.utils import extend_schema_field
import logging

logger = logging.getLogger(__name__)


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        logger.info('MyTokenObtainPairSerializer.get_token called for user=%s id=%s', user.username, user.id)
        token = super().get_token(user)
        token['username'] = user.username
        
        # Add role to token for dashboard middleware
        from .roles import get_user_role
        token['role'] = get_user_role(user)
        
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        from .views import _serialize_current_user
        data['user'] = _serialize_current_user(self.user)
        return data


class MyTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Issue access tokens that include `role` and `username` (same as login) so
    Next.js middleware and clients stay consistent after refresh.
    """

    def validate(self, attrs):
        refresh = RefreshToken(attrs["refresh"])
        uid = refresh.get(api_settings.USER_ID_CLAIM)
        if uid is None:
            raise InvalidToken(_("Token contained no recognizable user identification"))

        try:
            user = User.objects.get(**{api_settings.USER_ID_FIELD: uid})
        except User.DoesNotExist as exc:
            raise InvalidToken(_("User not found")) from exc

        access = refresh.access_token
        access["role"] = get_user_role(user)
        access["username"] = user.username

        data = {"access": str(access)}

        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass
            refresh.set_jti()
            refresh.set_exp(from_time=datetime.now(timezone.utc))
            refresh.set_iat(at_time=datetime.now(timezone.utc))
            data["refresh"] = str(refresh)

        if api_settings.UPDATE_LAST_LOGIN:
            user.last_login = datetime.now(timezone.utc)
            user.save(update_fields=["last_login"])

        return data


class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = ['id', 'label', 'address_line', 'city', 'phone', 'is_default', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()
    seller_profile = serializers.SerializerMethodField()
    addresses = UserAddressSerializer(many=True, read_only=True)
    role = serializers.SerializerMethodField()
    groups = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_staff', 'is_superuser', 'date_joined',
            'last_login', 'profile', 'seller_profile', 'addresses', 'role', 'groups'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']

    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_profile(self, obj):
        try:
            profile = obj.profile
            return {
                'name': profile.name,
                'phone_number': profile.phone_number,
                'address': profile.address,
                'image': profile.image.url if profile.image else None,
                'code': profile.code,
                'created_at': profile.created_at,
                'notification_orders': profile.notification_orders,
                'notification_promotions': profile.notification_promotions,
                'notification_messages': profile.notification_messages,
                'seller_notification_language': getattr(
                    profile, 'seller_notification_language', 'sw'
                ),
            }
        except Exception:
            return None

    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_seller_profile(self, obj):
        try:
            sp = obj.seller_profile
            if not sp:
                return None
            return {
                'id': sp.id,
                'business_name': sp.business_name,
                'business_type': sp.business_type,
                'is_verified': sp.is_verified,
                'is_active': sp.is_active,
                'store_description': sp.store_description,
                'notification_orders': sp.notification_orders,
                'notification_messages': sp.notification_messages,
                'notification_reviews': sp.notification_reviews,
                'notification_marketing': sp.notification_marketing,
                'auto_accept_orders': sp.auto_accept_orders,
                'require_phone_confirmation': sp.require_phone_confirmation,
                'shipping_method': sp.shipping_method,
                'return_policy': sp.return_policy,
            }
        except Exception:
            return None

    @extend_schema_field(serializers.CharField())
    def get_role(self, obj):
        return get_user_role(obj)


class UserProfileSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'name', 'phone_number', 'address', 'image', 'code', 'created_at',
            'notification_orders', 'notification_promotions', 'notification_messages',
            'seller_notification_language',
        ]
        read_only_fields = ['id', 'user', 'code', 'created_at']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)
    phone_number = serializers.CharField(required=True)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    role = serializers.ChoiceField(
        choices=['buyer', 'seller', 'both'],
        default='buyer',
        required=False,
    )

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'phone_number',
            'password',
            'password_confirm',
            'first_name',
            'last_name',
            'role',
        ]

    def to_internal_value(self, data):
        # Support aliases for password fields for backward compatibility
        if 'password1' in data and 'password' not in data:
            data['password'] = data['password1']
        if 'password2' in data and 'password_confirm' not in data:
            data['password_confirm'] = data['password2']
        if ('confirmPassword' in data or 'confirm_password' in data) and 'password_confirm' not in data:
            data['password_confirm'] = data.get('confirmPassword') or data.get('confirm_password')
        return super().to_internal_value(data)

    def validate_password(self, value):
        """Validate password strength."""
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError("Password must contain at least one number.")
        if not any(char.isalpha() for char in value):
            raise serializers.ValidationError("Password must contain at least one letter.")
        return value

    def validate_email(self, value):
        """Validate email format and uniqueness."""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_username(self, value):
        """Validate username format and uniqueness."""
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters long.")
        if not value.replace('_', '').replace('-', '').isalnum():
            raise serializers.ValidationError("Username can only contain letters, numbers, hyphens, and underscores.")
        return value

    def validate_phone_number(self, value):
        """Validate phone number format."""
        if value:
            cleaned = value.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+', '')
            if not cleaned.isdigit() or len(cleaned) < 9:
                raise serializers.ValidationError("Please enter a valid phone number.")
        return value

    def validate(self, data):
        if data.get('password') != data.get('password_confirm'):
            raise serializers.ValidationError({
                "password": "Passwords do not match.",
                "password_confirm": "Passwords do not match."
            })
        return data

    def create(self, validated_data):
        from core.services.accounts import AccountService
        return AccountService.register_user(validated_data)