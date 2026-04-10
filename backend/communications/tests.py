from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from communications.models import Conversation, Message
from accounts.models import Profile

class CommunicationsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_password = 'testpassword123'
        
        self.user = User.objects.create_user(username='user1', email='user1@test.com', password=self.user_password)
        self.agent = User.objects.create_user(username='agent1', email='agent1@test.com', password=self.user_password)
        self.user3 = User.objects.create_user(username='user3', email='user3@test.com', password=self.user_password)

        # Ensure profiles
        for u in [self.user, self.agent, self.user3]:
            if not hasattr(u, 'profile'):
                Profile.objects.create(user=u)

        # Create existing conversation
        self.conversation = Conversation.objects.create(
            user=self.user,
            agent=self.agent
        )
        
    def test_start_conversation(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('conversation-start-conversation')
        data = {
            'agent_id': self.user3.id  # Starting convo with user3 (treating as agent/target)
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Conversation.objects.count(), 2)
        
        # Test duplicate start returns existing
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Returns 201/200 but typically same serializer
        self.assertEqual(Conversation.objects.count(), 2) # Should not create new one
        self.assertEqual(response.data['id'], Conversation.objects.get(user=self.user, agent=self.user3).id)

    def test_send_message(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('conversation-send-message', args=[self.conversation.id])
        data = {'text': 'Hello Agent'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Message.objects.first().text, 'Hello Agent')

    def test_get_messages(self):
        # Create some messages
        Message.objects.create(conversation=self.conversation, sender=self.user, text="Hi")
        Message.objects.create(conversation=self.conversation, sender=self.agent, text="Hello User")
        
        self.client.force_authenticate(user=self.user)
        url = reverse('conversation-messages', args=[self.conversation.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_unread_count(self):
        # Agent sends message to User
        Message.objects.create(conversation=self.conversation, sender=self.agent, text="Unread Msg")
        
        self.client.force_authenticate(user=self.user)
        url = reverse('conversation-unread-count')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 1)

    def test_non_participant_access(self):
        self.client.force_authenticate(user=self.user3)
        url = reverse('conversation-messages', args=[self.conversation.id])
        response = self.client.get(url)
        # View catches Http404/Exception and returns 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
