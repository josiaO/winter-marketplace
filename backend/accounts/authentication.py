import logging
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from django.contrib.auth.models import User
import firebase_admin
from firebase_admin import auth

logger = logging.getLogger(__name__)

class FirebaseAuthentication(BaseAuthentication):
    """
    Firebase Authentication backend for Django Rest Framework.
    Verifies the JWT (ID Token) provided by Firebase and creates
    or retrieves the corresponding Django User.
    """
    keyword = 'bearer'

    def authenticate_header(self, request):
        return 'Bearer realm="api"'

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != self.keyword:
            return None

        id_token = parts[1]
        
        try:
            # Verify the token using Firebase Admin SDK
            decoded_token = auth.verify_id_token(id_token)
        except (auth.InvalidIdTokenError, ValueError):
            # Not a valid Firebase token, let other backends (like SimpleJWT) try
            return None
        except auth.ExpiredIdTokenError:
            raise exceptions.AuthenticationFailed('Firebase ID token has expired')
        except Exception as e:
            logger.error(f"Firebase auth verification failed: {e}")
            raise exceptions.AuthenticationFailed('Authentication process failed')

        uid = decoded_token.get('uid')
        email = decoded_token.get('email')
        email_verified = decoded_token.get('email_verified')
        
        if email and not email_verified:
            raise exceptions.AuthenticationFailed('Please verify your email address before logging in.')
        
        if not uid:
            raise exceptions.AuthenticationFailed('Token contains no UID')
            
        try:
            # Look up the user by Profile's firebase_uid
            from accounts.models import Profile
            profile = Profile.objects.get(firebase_uid=uid)
            user = profile.user
            
            # Optionally update email if it changed in Firebase
            if email and user.email != email:
                user.email = email
                user.save(update_fields=['email'])
                
        except Profile.DoesNotExist:
            # If no profile with this UID exists, see if user exists by email
            if email:
                # Try to get existing user or create a new one
                user, created = User.objects.get_or_create(username=email, defaults={'email': email})
                # Link or create profile
                if hasattr(user, 'profile'):
                    profile = user.profile
                    profile.firebase_uid = uid
                    profile.save(update_fields=['firebase_uid'])
                else:
                    Profile.objects.create(user=user, firebase_uid=uid)
            else:
                # Phone auth or anonymous might not have email
                # Create a user with uid as username
                user = User.objects.create(username=uid)
                Profile.objects.create(user=user, firebase_uid=uid)
                
        if not user.is_active:
            raise exceptions.AuthenticationFailed('User account is disabled')

        return (user, decoded_token)