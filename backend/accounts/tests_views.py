from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User, Group
from accounts.models import Profile
from properties.models import AgentProfile

class AccountsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_password = 'testpassword123'
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password=self.user_password)
        self.admin = User.objects.create_superuser(username='admin', email='admin@example.com', password=self.user_password)
        
        # Ensure profiles exist
        if not hasattr(self.user, 'profile'):
            Profile.objects.create(user=self.user)
        if not hasattr(self.admin, 'profile'):
            Profile.objects.create(user=self.admin)

        # Create agent user
        self.agent = User.objects.create_user(username='agent', email='agent@example.com', password=self.user_password)
        agent_group, _ = Group.objects.get_or_create(name='agent')
        self.agent.groups.add(agent_group)
        if not hasattr(self.agent, 'profile'):
             Profile.objects.create(user=self.agent)
        AgentProfile.objects.create(user=self.agent, profile=self.agent.profile)

    def test_login(self):
        url = reverse('accounts:token_obtain_pair')
        data = {
            'username': 'testuser',
            'password': self.user_password
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_register(self):
        url = reverse('accounts:register')
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'phone_number': '0755123456',
            'password': 'newpassword123',
            'password1': 'newpassword123',
            'password2': 'newpassword123',
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='newuser').exists())
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)

    def test_get_current_user_profile(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('accounts:me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertIn('profile', response.data)

    def test_update_profile(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('accounts:me')
        data = {
            'profile_name': 'Updated Name',
            'phone_number': '1234567890'
        }
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.name, 'Updated Name')
        self.assertEqual(self.user.profile.phone_number, '1234567890')

    def test_admin_user_stats(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('accounts:user-management-stats') # Check router generated name
        # router.register(r'users', views.UserManagementViewSet, basename='user-management')
        # stats action url is likely list url + 'stats/' or custom action.
        # @action(detail=False, methods=['get']) def stats(self, request):
        # Name should be 'user-management-stats'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_users', response.data)

    def test_login_with_non_existent_email(self):
        """Test that login with non-existent email returns 401 instead of 400."""
        url = reverse('accounts:token_obtain_pair')
        data = {
            'email': 'nonexistent@example.com',
            'password': 'somepassword'
        }
        response = self.client.post(url, data, format='json')
        # Should be 401 Unauthorized, not 400 Bad Request (which happened if username was missing)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['error'], 'Invalid credentials. Please check your email/username and password.')
