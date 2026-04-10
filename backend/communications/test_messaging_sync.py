"""
Test to verify messaging system synchronization:
- New messages appear in real-time
- Reading a conversation clears related notifications
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from communications.models import Conversation, Message, Notification
from communications.views import ConversationViewSet
from rest_framework.test import APIRequestFactory
from accounts.models import Profile

User = get_user_model()


class MessagingSyncTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='pass')
        self.agent = User.objects.create_user(username='agent', email='agent@example.com', password='pass')
        
        # Ensure profiles exist
        for u in [self.user, self.agent]:
            if not hasattr(u, 'profile'):
                Profile.objects.create(user=u)
        
        self.conversation = Conversation.objects.create(user=self.user, agent=self.agent)
        
        # Create a message from agent to user
        self.message = Message.objects.create(
            conversation=self.conversation,
            sender=self.agent,
            text="Hello from agent"
        )
        
        # Create a notification for the user about this message
        self.notification = Notification.objects.create(
            user=self.user,
            type='message',
            title='New Message',
            message='You have a new message',
            related_object_id=self.conversation.id,
            related_object_type='conversation',
            is_read=False
        )
    
    def test_mark_read_clears_notifications(self):
        """Test that marking a conversation as read also marks related notifications as read"""
        from rest_framework.test import APIClient
        
        # Verify notification is unread
        self.assertFalse(self.notification.is_read)
        
        # Create authenticated client
        client = APIClient()
        client.force_authenticate(user=self.user)
        
        # Call the mark_read endpoint
        response = client.post(f'/api/v1/communications/conversations/{self.conversation.id}/mark_read/')
        
        # Verify response is successful
        self.assertEqual(response.status_code, 200)
        
        # Refresh notification from DB
        self.notification.refresh_from_db()
        
        # Verify notification is now marked as read
        self.assertTrue(self.notification.is_read, "Notification should be marked as read when conversation is read")
    
    def test_multiple_notifications_cleared(self):
        """Test that multiple notifications for the same conversation are all marked as read"""
        from rest_framework.test import APIClient
        
        # Create another notification for the same conversation
        notification2 = Notification.objects.create(
            user=self.user,
            type='message',
            title='Another Message',
            message='Another new message',
            related_object_id=self.conversation.id,
            related_object_type='conversation',
            is_read=False
        )
        
        # Create authenticated client
        client = APIClient()
        client.force_authenticate(user=self.user)
        
        # Mark conversation as read
        response = client.post(f'/api/v1/communications/conversations/{self.conversation.id}/mark_read/')
        
        self.assertEqual(response.status_code, 200)
        
        # Refresh both notifications
        self.notification.refresh_from_db()
        notification2.refresh_from_db()
        
        # Both should be marked as read
        self.assertTrue(self.notification.is_read)
        self.assertTrue(notification2.is_read)
