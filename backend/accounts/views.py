from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.types import OpenApiTypes
from django.http import JsonResponse
import logging
logger = logging.getLogger(__name__)
import json
import secrets
from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError
from django.db import transaction
from core.permissions import IsAdmin, IsSeller
from datetime import timedelta
from .models import Profile
from .serializers import UserSerializer, UserProfileSerializer
from .forms import SignupForm, ActivationForm
from .roles import get_user_role, is_seller
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework.views import APIView
from core.services.accounts import AccountService
from .models import Profile, UserAddress
from .serializers import (
    UserSerializer, UserProfileSerializer, UserAddressSerializer,
    RegisterSerializer, MyTokenObtainPairSerializer
)
from commerce.models import Order
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample, inline_serializer
from .otp import verify_otp as _verify_otp, send_otp as _send_otp
from .throttles import AuthLoginThrottle, AuthRefreshThrottle
try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth
except ImportError:
    firebase_admin = None
    firebase_auth = None


class UserManagementViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    # Only superusers (admin) should manage users
    permission_classes = [IsAdmin]

    def get_queryset(self):
        queryset = User.objects.all().select_related('profile').prefetch_related('groups')

        # Filter by role
        role = self.request.query_params.get('role')
        if role == 'seller':
            queryset = queryset.filter(groups__name='seller')
        elif role == 'buyer' or role == 'user':
            queryset = queryset.exclude(groups__name='seller').exclude(is_superuser=True)
        elif role == 'admin':
            queryset = queryset.filter(is_superuser=True)

        # Search by username or email
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)
            )

        return queryset.order_by('-date_joined')

    @action(detail=True, methods=['post'])
    def toggle_seller_status(self, request, pk=None):
        """Toggle seller status for a user"""
        user = self.get_object()
        if is_seller(user):
            _, message = AccountService.downgrade_from_seller(user)
        else:
            _, message = AccountService.toggle_seller_role(user)
        return Response({'message': message})

    @action(detail=True, methods=['post'])
    def toggle_active_status(self, request, pk=None):
        """Toggle active status for a user"""
        user = self.get_object()
        user.is_active = not user.is_active
        user.save()

        status_text = "activated" if user.is_active else "deactivated"
        return Response({'message': f"{user.username} has been {status_text}"})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get user statistics"""
        stats = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'sellers': User.objects.filter(groups__name='seller').count(),
            'buyers': User.objects.exclude(groups__name='seller').exclude(is_superuser=True).count(),
            'admins': User.objects.filter(is_superuser=True).count(),
            'users_with_profiles': User.objects.filter(profile__isnull=False).count(),
            'recent_signups': User.objects.filter(
                date_joined__gte=timezone.now() - timedelta(days=30)
            ).count(),
        }
        # Monthly signup stats (last 6 months approximate)
        monthly_stats = []
        for i in range(6):
            month_start = timezone.now() - timedelta(days=30 * i)
            month_end = month_start + timedelta(days=30)
            count = User.objects.filter(
                date_joined__gte=month_start,
                date_joined__lt=month_end
            ).count()
            monthly_stats.append({
                'month': month_start.strftime('%b'),
                'count': count
            })

        stats['monthly_signups'] = monthly_stats

        return Response(stats)


class UserAddressViewSet(viewsets.ModelViewSet):
    serializer_class = UserAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return UserAddress.objects.none()
        return UserAddress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserProfileViewSet(viewsets.ModelViewSet):

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Profile.objects.none()
        if self.request.user.is_superuser:
            return Profile.objects.all()
        else:
            return Profile.objects.filter(user=self.request.user)

    def get_object(self):
        if self.request.user.is_superuser:
            return super().get_object()
        else:
            return self.request.user.profile

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save()


class MyTokenObtainPairView(TokenObtainPairView):
    authentication_classes = []
    serializer_class = MyTokenObtainPairSerializer
    throttle_classes = [AuthLoginThrottle]

    def post(self, request, *args, **kwargs):
        """Allow clients to POST either {'username','password'} or {'email','password'}."""

        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)

        # Avoid logging raw identifiers (email/username) to reduce PII exposure.
        logger.info(
            "TokenObtain: login attempt (has_email=%s, has_username=%s)",
            bool(data.get("email")),
            bool(data.get("username")),
        )

        if 'email' in data and 'username' not in data:
            UserModel = get_user_model()
            try:
                email_input = data.get('email', '').strip()
                if not email_input:
                    return Response(
                        {'error': 'Email or Username is required'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                u = UserModel.objects.filter(email__iexact=email_input).first()
                if u:
                    data['username'] = u.get_username()
                else:
                    data['username'] = email_input
                    logger.warning(f"TokenObtain: Failed to resolve email {email_input}")
            except Exception as e:
                logger.error(f"TokenObtain: Error during email resolution: {str(e)}")

        serializer = self.get_serializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)

            if hasattr(serializer, 'user'):
                logger.info(f"TokenObtain: Login successful for user_id={serializer.user.id}")

            return Response(serializer.validated_data, status=status.HTTP_200_OK)

        except ValidationError as ve:
            error_messages = {}
            if hasattr(ve, 'detail'):
                if isinstance(ve.detail, dict):
                    error_messages = ve.detail
                else:
                    error_messages = {'non_field_errors': ve.detail}
            else:
                error_messages = {'non_field_errors': [str(ve)]}

            logger.warning(f"TokenObtain: Login validation failed. Errors: {error_messages}")
            return Response(
                {'error': error_messages},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.warning(f"TokenObtain: Login failed. Error: {str(e)}")
            return Response(
                {'error': 'Invalid credentials. Please check your email/username and password.'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class MyTokenRefreshView(TokenRefreshView):
    """Token refresh view with rate limiting enabled."""

    throttle_classes = [AuthRefreshThrottle]


@extend_schema(responses={200: OpenApiTypes.STR})
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def get_user_routes(request):
    routes = [
        '/api/v1/accounts/auth/token/',
        '/api/v1/accounts/auth/token/refresh/',
    ]
    return Response(routes)





@extend_schema(
    request=inline_serializer("LogoutRequest", fields={"refresh": serializers.CharField()}),
    responses={205: None}
)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def auth_logout(request):
    """Logout endpoint - blacklist refresh token"""
    try:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(status=status.HTTP_205_RESET_CONTENT)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception as e:
            logger.warning('Logout: could not blacklist token: %s', str(e))
        return Response(status=status.HTTP_205_RESET_CONTENT)
    except Exception as e:
        logger.error('Logout failed: %s', str(e))
        return Response(status=status.HTTP_205_RESET_CONTENT)


@extend_schema(
    request=inline_serializer("FirebaseLoginRequest", fields={
        "firebase_token": serializers.CharField(),
        "firebase_uid": serializers.CharField(),
        "email": serializers.EmailField(),
        "display_name": serializers.CharField(required=False),
        "phone_number": serializers.CharField(required=False),
    }),
    responses={200: OpenApiTypes.OBJECT}
)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def firebase_login(request):
    """
    Firebase authentication endpoint.
    Receives Firebase ID token and exchanges it for Django JWT tokens.
    Creates/updates user in database based on Firebase user data.
    """
    try:
        User = get_user_model()

        firebase_token = request.data.get('firebase_token')
        firebase_uid = request.data.get('firebase_uid')
        email = request.data.get('email')
        display_name = request.data.get('display_name')
        phone_number = request.data.get('phone_number')

        if not firebase_token or not firebase_uid:
            return Response(
                {'error': 'firebase_token and firebase_uid are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not email:
            return Response(
                {'error': 'email is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify Firebase token
        try:
            if not firebase_auth:
                raise ImportError("Firebase admin not installed")
            decoded_token = firebase_auth.verify_id_token(firebase_token)

            if decoded_token.get('uid') != firebase_uid:
                return Response(
                    {'error': 'Firebase token UID mismatch'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            logger.info(f'Firebase token verified for UID: {firebase_uid}')

        except firebase_admin.exceptions.FirebaseError as e:
            logger.error(f'Firebase token verification failed: {str(e)}')
            return Response(
                {'error': 'Invalid Firebase token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(f'An unexpected error occurred during Firebase verification: {str(e)}')
            return Response(
                {'error': 'Could not verify authentication credentials.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Create or get user
        try:
            user, created = AccountService.firebase_authenticate({
                'email': email,
                'firebase_uid': firebase_uid,
                'display_name': display_name,
                'phone_number': phone_number
            })
            logger.info(f'User {"created" if created else "updated"} for Firebase UID: {firebase_uid}')
        except Exception as e:
            logger.error(f'User creation/update failed: {str(e)}', exc_info=True)
            return Response(
                {'error': 'Failed to create/update user'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Generate JWT tokens
        try:
            refresh = RefreshToken.for_user(user)
            
            # Add role to token for dashboard middleware
            refresh['role'] = get_user_role(user)
            
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            return Response({
                'access': access_token,
                'refresh': refresh_token,
                'user': _serialize_current_user(user)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f'Token generation failed: {str(e)}')
            return Response(
                {'error': 'Failed to generate tokens'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        logger.error(f'Firebase login endpoint error: {str(e)}')
        return Response(
            {'error': 'Authentication failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    request=RegisterSerializer,
    responses={201: OpenApiTypes.OBJECT}
)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def register(request):
    """
    Unified registration endpoint using RegisterSerializer.
    Handles user registration - all new users are buyers by default.
    """
    serializer = RegisterSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = serializer.save()
        logger.info(f"User registered successfully: {user.username} (ID: {user.id})")

        # We DO NOT return tokens here because the user is inactive (is_active=False)
        # and needs to verify via OTP first.
        
        return Response(
            {
                'success': True,
                'message': 'User created successfully. Please verify your account using OTP.',
                'user_id': user.id,
                'email': user.email,
                'phone': user.profile.phone_number if hasattr(user, 'profile') else None,
                'username': user.username,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error(f"Registration failed: {str(e)}", exc_info=True)
        return Response({'error': 'An unexpected error occurred during registration.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _serialize_current_user(user):
    profile = getattr(user, 'profile', None)
    profile_data = None
    if profile:
        profile_data = {
            'name': profile.name,
            'phone_number': profile.phone_number,
            'address': profile.address,
            'image': profile.image.url if profile.image else None,
        }

    role = get_user_role(user)
    is_seller_flag = is_seller(user)

    # Check for seller_profile (marketplace seller)
    seller_profile_data = None
    try:
        seller_profile = getattr(user, 'seller_profile', None)
        if seller_profile:
            seller_profile_data = {
                'id': seller_profile.id,
                'business_name': seller_profile.business_name or None,
                'business_type': seller_profile.business_type or None,
                'is_verified': bool(seller_profile.is_verified),
                'verified_at': seller_profile.verified_at.isoformat() if seller_profile.verified_at else None,
                'is_active': bool(seller_profile.is_active),
            }
    except Exception:
        pass

    user_summary = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'phone': profile.phone_number if profile else None,
        'orders_count': Order.objects.filter(buyer=user).count(),
    }

    response = {
        **user_summary,
        'role': role,
        'isAuthenticated': True,
        'is_superuser': user.is_superuser,
        'is_staff': user.is_staff,
        'is_seller': is_seller_flag,
        'groups': list(user.groups.values_list('name', flat=True)),
        'profile': profile_data,
        'seller_profile': seller_profile_data,
        'user': user_summary,
    }
    return response


def _update_current_user_profile(request):
    try:
        user = AccountService.update_profile(request.user, request.data, request.FILES)
    except ValidationError as ve:
        return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        logger.error(f"Profile update failed for {request.user.username}: {str(exc)}")
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_serialize_current_user(user))


@extend_schema(
    methods=['GET'],
    operation_id="api_v1_accounts_me_retrieve",
    responses={200: UserProfileSerializer}
)
@extend_schema(
    methods=['PUT'],
    operation_id="api_v1_accounts_me_update",
    request=UserProfileSerializer,
    responses={200: UserProfileSerializer}
)
@extend_schema(
    methods=['PATCH'],
    operation_id="api_v1_accounts_me_partial_update",
    request=UserProfileSerializer,
    responses={200: UserProfileSerializer}
)
@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Retrieve or update the authenticated user's profile in a single endpoint."""
    if request.method == 'GET':
        try:
            return Response(_serialize_current_user(request.user))
        except Exception as e:
            return Response({'error': str(e)}, status=500)
    return _update_current_user_profile(request)


@extend_schema(
    request=UserProfileSerializer,
    responses={200: UserProfileSerializer}
)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    """Legacy endpoint that now delegates to the consolidated /accounts/me/ handler."""
    return _update_current_user_profile(request)


def signup(request):
    """Register a new user. Creates an inactive user and sends activation code via email."""
    if request.method == 'POST':
        form = SignupForm(request.POST, request.FILES)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']

            user = form.save(commit=False)
            user.is_active = False
            user.save()

            profile = user.profile

            # Send an activation email
            send_mail(
                "Activate Your Account",
                f"Welcome {username}\nUse this code {profile.code} to activate your account.",
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )
            return redirect(f'/accounts/{username}/activate')

    else:
        form = SignupForm()
    return render(request, 'registration/register.html', {'form': form})


def activate(request, username):
    """Activate a user when they submit the activation code."""
    user = get_object_or_404(User, username=username)
    profile = user.profile

    if request.method == 'POST':
        if (request.content_type and 'application/json' in request.content_type) or request.headers.get('Accept', '').startswith('application/json'):
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except Exception:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
            code = payload.get('code')
            if code and code == profile.code:
                profile.code = ''
                profile.save()
                user.is_active = True
                user.save()
                return JsonResponse({'message': 'Account activated'})
            return JsonResponse({'error': 'Invalid activation code'}, status=400)

        form = ActivationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            if code == profile.code:
                profile.code = ''
                profile.save()

                user.is_active = True
                user.save()

                return redirect('/accounts/login')
    else:
        form = ActivationForm()

    return render(request, 'registration/activate.html', {'form': form})


@login_required
def profile_view(request):
    """Render the logged-in user's profile."""
    user_pk = request.user.pk
    profile = User.objects.get(pk=user_pk)
    return render(request, 'account/profile.html', {'profile': profile, 'request': request})


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    
    @extend_schema(
        request=inline_serializer("PasswordResetRequest", fields={"email": serializers.EmailField()}),
        responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request):
        form = PasswordResetForm(request.data)
        if form.is_valid():
            email = form.cleaned_data["email"]
            users = form.get_users(email)
            if users:
                for user in users:
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    token = default_token_generator.make_token(user)

                    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
                    reset_link = f"{frontend_url}/reset-password/{uid}/{token}"

                    try:
                        from .tasks import send_password_reset_email_task
                        send_password_reset_email_task.delay(user.id, reset_link)
                    except Exception as e:
                        logger.error(f"Failed to enqueue password reset email task for {user.email}: {e}")

            return Response({'message': 'Password reset email sent if account exists.'})
        else:
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=inline_serializer("PasswordResetConfirmRequest", fields={
            "uid": serializers.CharField(),
            "token": serializers.CharField(),
            "new_password": serializers.CharField(),
            "re_new_password": serializers.CharField(),
        }),
        responses={200: OpenApiTypes.OBJECT}
    )
    def post(self, request):
        uidb64 = request.data.get('uid')
        token = request.data.get('token')
        password = request.data.get('new_password')
        re_password = request.data.get('re_new_password')

        if not all([uidb64, token, password, re_password]):
            return Response({'error': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)

        if password != re_password:
            return Response({'error': 'Passwords do not match'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and default_token_generator.check_token(user, token):
            user.set_password(password)
            user.save()
            return Response({'message': 'Password has been reset successfully.'})
        else:
            return Response({'error': 'Invalid link or expired token'}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    request=inline_serializer("ChangePasswordRequest", fields={
        "old_password": serializers.CharField(),
        "new_password": serializers.CharField(),
        "confirm_password": serializers.CharField(),
    }),
    responses={200: OpenApiTypes.OBJECT}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change password for authenticated user."""
    user = request.user
    data = request.data

    old_password = data.get('old_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    if not old_password or not new_password:
        return Response({'error': 'Old and new passwords are required'}, status=status.HTTP_400_BAD_REQUEST)

    if not user.check_password(old_password):
        return Response({'error': 'Invalid old password'}, status=status.HTTP_400_BAD_REQUEST)

    if new_password != confirm_password:
        return Response({'error': 'New passwords do not match'}, status=status.HTTP_400_BAD_REQUEST)

    if len(new_password) < 8:
        return Response({'error': 'Password must be at least 8 characters long'}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()

    return Response({'message': 'Password changed successfully'})


@extend_schema(
    request=inline_serializer("DeleteAccountRequest", fields={"code": serializers.CharField()}),
    responses={200: OpenApiTypes.OBJECT}
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_account(request):
    """
    Delete authenticated user's account — REQUIRES OTP.
    
    DELETE body: { "code": "123456" }
    """
    user = request.user
    code = request.data.get('code')
    
    if not code:
        return Response({'error': 'Verification code is required to delete account'}, status=status.HTTP_400_BAD_REQUEST)

    success, message = _verify_otp(user, code=code, purpose='delete_account')
    
    if not success:
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Soft-delete: deactivate user and mark profile as deleted
        user.is_active = False
        user.save()
        
        profile = getattr(user, 'profile', None)
        if profile:
            profile.is_deleted = True
            profile.save()
        
        # Blacklist current tokens if using SimpleJWT
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass

        logger.info(f"User {user.username} (ID: {user.id}) has deleted their account.")
        return Response({'message': 'Account successfully deleted (deactivated).'})
    except Exception as e:
        logger.error(f"Error during account deletion for user {user.id}: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    request=None,
    responses={
        200: inline_serializer("UpgradeToSellerResponse", fields={
            "message": serializers.CharField(),
            "seller_profile_id": serializers.IntegerField(allow_null=True),
            "already_seller": serializers.BooleanField(),
            "access": serializers.CharField(),
            "refresh": serializers.CharField(),
            "user": OpenApiTypes.OBJECT,
        })
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upgrade_to_seller(request):
    """Upgrade a regular user to a seller and return fresh JWTs (role in token must match DB for dashboard middleware)."""
    try:
        user = request.user
        already = is_seller(user)

        if not already:
            _, message = AccountService.toggle_seller_role(user)
        else:
            message = 'User is already a seller'

        user.refresh_from_db()
        seller_profile = getattr(user, 'seller_profile', None)

        refresh = RefreshToken.for_user(user)
        refresh['role'] = get_user_role(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        return Response({
            'message': message,
            'seller_profile_id': seller_profile.id if seller_profile else None,
            'already_seller': already,
            'access': access_token,
            'refresh': refresh_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name or '',
                'last_name': user.last_name or '',
                'is_active': user.is_active,
                'role': get_user_role(user),
                'seller_profile': {'id': seller_profile.id} if seller_profile else None,
            },
        })
    except Exception as e:
        logger.exception("Error in upgrade_to_seller")
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ────────────────────────────────────────────────
# OTP: Email / Action Verification
# ────────────────────────────────────────────────

@extend_schema(
    request=inline_serializer("RequestOTPRequest", fields={
        "purpose": serializers.CharField(),
        "email": serializers.EmailField(required=False),
        "channel": serializers.CharField(required=False),
    }),
    responses={200: OpenApiTypes.OBJECT}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def request_otp(request):
    """
    Request a new OTP for the given purpose.
    For 'verify_email' and 'confirm_action' the caller must be authenticated.
    For 'password_reset' the caller supplies their email address.
    
    POST body: { "purpose": "verify_email" | "password_reset" | "confirm_action", "email": "..." }
    """
    purpose = request.data.get('purpose', 'verify_email')
    channel = request.data.get('channel', 'email') # 'email' or 'sms'
    valid_purposes = ['verify_email', 'password_reset', 'confirm_action', 'delete_account']
    
    if purpose not in valid_purposes:
        return Response({'error': f'Invalid purpose. Choose from: {valid_purposes}'}, status=400)

    if purpose == 'password_reset':
        email = request.data.get('email', '').strip()
        if not email:
            return Response({'error': 'email is required for password_reset OTP'}, status=400)
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({'message': 'If that email exists, an OTP has been sent.'})
    elif purpose == 'verify_email' and not request.user.is_authenticated:
        # Allow unauthenticated OTP requests for email/phone verification if user_id or email provided
        user_id = request.data.get('user_id')
        email = request.data.get('email')
        User = get_user_model()
        if user_id:
            user = User.objects.filter(id=user_id).first()
        elif email:
            user = User.objects.filter(email__iexact=email).first()
        else:
            return Response({'error': 'user_id or email is required for unauthenticated OTP request'}, status=400)
            
        if not user:
            return Response({'error': 'User not found'}, status=404)
    else:
        # confirm_action and delete_account require authentication
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required for this OTP purpose.'}, status=401)
        user = request.user

    try:
        _send_otp(user, purpose=purpose, channel=channel)
        return Response({
            'message': f'OTP sent via {channel}.',
            'expires_in_minutes': getattr(settings, 'OTP_EXPIRY_MINUTES', 10)
        })
    except Exception as e:
        logger.error(f'Failed to send OTP for user {user.email} via {channel}: {e}')
        return Response({'error': 'Failed to send OTP. Please try again.'}, status=500)


@extend_schema(
    request=inline_serializer("VerifyOTPRequest", fields={
        "code": serializers.CharField(),
        "purpose": serializers.CharField(required=False),
        "email": serializers.EmailField(required=False),
        "user_id": serializers.IntegerField(required=False),
    }),
    responses={
        200: inline_serializer("VerifyOTPResponse", fields={
            "message": serializers.CharField(),
            "verified": serializers.BooleanField(required=False),
            "reset_token": serializers.CharField(required=False),
        })
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    """
    Verify the OTP code supplied by the user.
    
    POST body: { "code": "123456", "purpose": "verify_email", "email": "...(for pwd reset)" }
    """
    
    code = (request.data.get('code') or request.data.get('otp') or '').strip()
    purpose = request.data.get('purpose', 'verify_email')
    
    if not code:
        return Response({'error': 'code is required'}, status=400)

    if purpose == 'password_reset':
        email = request.data.get('email', '').strip()
        if not email:
            return Response({'error': 'email is required for password_reset verification'}, status=400)
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({'error': 'Invalid email or OTP.'}, status=400)
    elif purpose == 'verify_email' and not request.user.is_authenticated:
        user_id = request.data.get('user_id')
        email = request.data.get('email')
        User = get_user_model()
        if user_id:
            user = User.objects.filter(id=user_id).first()
        elif email:
            user = User.objects.filter(email__iexact=email).first()
        else:
            return Response({'error': 'user_id or email is required'}, status=400)
            
        if not user:
            return Response({'error': 'User not found'}, status=404)
    else:
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=401)
        user = request.user

    success, message = _verify_otp(user, code=code, purpose=purpose)

    if success:
        # For password_reset, return a short-lived confirmation token
        if purpose == 'password_reset':
            confirmation_token = secrets.token_urlsafe(32)
            cache.set(f'otp_pwd_reset_{user.id}', confirmation_token, timeout=300)  # 5 min
            return Response({'message': message, 'reset_token': confirmation_token})
        return Response({'message': message, 'verified': True})
    else:
        return Response({'error': message, 'verified': False}, status=400)


@extend_schema(
    request=inline_serializer("ChangePasswordWithOTPRequest", fields={
        "reset_token": serializers.CharField(),
        "new_password": serializers.CharField(),
        "confirm_password": serializers.CharField(),
    }),
    responses={200: OpenApiTypes.OBJECT}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_with_otp(request):
    """
    Change password after OTP verification.
    """
    user = request.user
    reset_token = request.data.get('reset_token', '')
    new_password = request.data.get('new_password', '')
    confirm_password = request.data.get('confirm_password', '')

    if not all([reset_token, new_password, confirm_password]):
        return Response({'error': 'reset_token, new_password and confirm_password are required'}, status=400)

    if new_password != confirm_password:
        return Response({'error': 'Passwords do not match'}, status=400)

    if len(new_password) < 8:
        return Response({'error': 'Password must be at least 8 characters long'}, status=400)

    cache_key = f'otp_pwd_reset_{user.id}'
    stored_token = cache.get(cache_key)

    if not stored_token or stored_token != reset_token:
        return Response({'error': 'Invalid or expired reset token. Please request a new OTP.'}, status=400)

    user.set_password(new_password)
    user.save()
    cache.delete(cache_key)

    logger.info(f'Password changed via OTP for user {user.email}')
    return Response({'message': 'Password changed successfully.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def issue_ws_ticket(request):
    """
    Issue a short-lived one-time ticket for WebSocket authentication.
    TTL is 60 seconds (handshake typically happens within 1s).
    """
    ticket = secrets.token_urlsafe(32)
    cache.set(f"ws_ticket_{ticket}", request.user.id, timeout=60)
    return Response({'ticket': ticket})
