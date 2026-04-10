from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
import base64
import json

from django.contrib.auth.models import User
from accounts.models import Profile


def _payload_from_jwt(access: str) -> dict:
    parts = access.split(".")
    if len(parts) != 3:
        return {}
    payload_b64 = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
    raw = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
    return json.loads(raw.decode("utf-8"))


class AccountsExtendedTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_password = 'testpassword123'
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password=self.user_password)
        if not hasattr(self.user, 'profile'):
            Profile.objects.create(user=self.user)

    def test_token_refresh(self):
        # Get token pair
        url = reverse('accounts:token_obtain_pair')
        data = {'username': 'testuser', 'password': self.user_password}
        response = self.client.post(url, data, format='json')
        refresh_token = response.data['refresh']
        
        # Refresh token
        refresh_url = reverse('accounts:token_refresh')
        response = self.client.post(refresh_url, {'refresh': refresh_token}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        payload = _payload_from_jwt(response.data["access"])
        self.assertIn("role", payload)
        self.assertEqual(payload.get("role"), "user")

    def test_logout(self):
        # Get token pair
        url = reverse('accounts:token_obtain_pair')
        data = {'username': 'testuser', 'password': self.user_password}
        response = self.client.post(url, data, format='json')
        refresh_token = response.data['refresh']
        
        # Logout (blacklist token)
        logout_url = reverse('accounts:auth_logout')
        response = self.client.post(logout_url, {'refresh': refresh_token}, format='json')
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        
        # Try to refresh with blacklisted token (should fail)
        refresh_url = reverse('accounts:token_refresh')
        response = self.client.post(refresh_url, {'refresh': refresh_token}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_register_duplicate_username(self):
        url = reverse('accounts:register')
        data = {
            'username': 'testuser',  # duplicate
            'email': 'new@example.com',
            'phone_number': '0755123456',
            'password': 'newpassword123',
            'password_confirm': 'newpassword123',
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_register_duplicate_email(self):
        url = reverse('accounts:register')
        data = {
            'username': 'newuser',
            'email': 'test@example.com',  # duplicate
            'phone_number': '0755123457',
            'password': 'newpassword123',
            'password_confirm': 'newpassword123',
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('accounts:change_password')
        data = {
            'old_password': self.user_password,
            'new_password': 'newpassword456',
            'confirm_password': 'newpassword456'
        }
        response = self.client.patch(url, data, format='json') # change_password allows PUT/PATCH usually
        
        # Check if the response is 200 or 204 or check logic in views
        if response.status_code == 405: # Method not allowed, maybe POST?
             response = self.client.post(url, data, format='json')
             
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify login with new password
        self.client.logout()
        login_url = reverse('accounts:token_obtain_pair')
        login_data = {'username': 'testuser', 'password': 'newpassword456'}
        response = self.client.post(login_url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
