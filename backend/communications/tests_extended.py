from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from communications.models import Conversation, Message
from accounts.models import Profile

class CommunicationsExtendedTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_password = 'testpassword123'
        
        self.user = User.objects.create_user(username='user1', email='user1@test.com', password=self.user_password)
        self.agent = User.objects.create_user(username='agent1', email='agent1@test.com', password=self.user_password)
        
        # Ensure profiles
        for u in [self.user, self.agent]:
            if not hasattr(u, 'profile'):
                Profile.objects.create(user=u)

        # Create existing conversation
        self.conversation = Conversation.objects.create(
            user=self.user,
            agent=self.agent
        )
        self.message = Message.objects.create(conversation=self.conversation, sender=self.agent, text="Hi")

    def test_clear_history(self):
        self.client.force_authenticate(user=self.user)
        
        # Verify conversation visible
        self.assertFalse(self.conversation.hidden_by.filter(id=self.user.id).exists())
        
        # Clear history
        url = reverse('conversation-clear-history', args=[self.conversation.id])
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify hidden
        self.assertTrue(self.conversation.hidden_by.filter(id=self.user.id).exists())
        self.assertTrue(self.message.hidden_by.filter(id=self.user.id).exists())

    def test_new_message_unhides_conversation(self):
        # Hide conversation
        self.conversation.hidden_by.add(self.user)
        
        # Agent sends new message
        self.client.force_authenticate(user=self.agent)
        url = reverse('conversation-send-message', args=[self.conversation.id])
        data = {'text': 'New Message'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify unhidden for user
        self.assertFalse(self.conversation.hidden_by.filter(id=self.user.id).exists())

    def test_delete_message_for_me(self):
        self.client.force_authenticate(user=self.user)
        
        url = reverse('message-delete-for-me', args=[self.message.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify hidden
        self.assertTrue(self.message.hidden_by.filter(id=self.user.id).exists())
