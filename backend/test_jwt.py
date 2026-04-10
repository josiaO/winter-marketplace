import os
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from django.conf import settings

def test_jwt():
    user = User.objects.first()
    if not user:
        print("No users found")
        return

    print(f"Testing for user: {user.username}")
    print(f"SECRET_KEY: {settings.SECRET_KEY}")
    print(f"SIMPLE_JWT SIGNING_KEY: {settings.SIMPLE_JWT.get('SIGNING_KEY')}")
    
    refresh = RefreshToken.for_user(user)
    access_token_str = str(refresh.access_token)
    print(f"Generated Token: {access_token_str[:20]}...")

    try:
        token = AccessToken(access_token_str)
        print("Token verification SUCCESSFUL")
        print(f"Token payload: {token.payload}")
    except Exception as e:
        print(f"Token verification FAILED: {e}")

if __name__ == "__main__":
    test_jwt()
