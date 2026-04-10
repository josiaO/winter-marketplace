from django.test import TestCase
from django.contrib.auth.models import User, Group
from accounts.models import Profile
from accounts.roles import get_user_role

class RoleTestCase(TestCase):
    def setUp(self):
        self.agent_group = Group.objects.create(name='agent')

    def test_user_role_creation(self):
        user = User.objects.create_user(username='testuser', password='password')
        # Signal should create profile with default role 'user'
        self.assertEqual(get_user_role(user), 'user')

    def test_agent_role_creation(self):
        user = User.objects.create_user(username='testagent', password='password')
        user.groups.add(self.agent_group)
        self.assertEqual(get_user_role(user), 'agent')

    def test_admin_role_creation(self):
        admin = User.objects.create_superuser(username='testadmin', password='password', email='admin@test.com')
        self.assertEqual(get_user_role(admin), 'admin')
