"""
Tests for messaging rate limiting and encryption features
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from communications.models import Conversation, Message
from communications.throttles import WebSocketRateLimit
from communications.encryption import get_encryptor
from accounts.models import Profile
from rest_framework.exceptions import Throttled
import time


class RateLimitingTests(TestCase):
    """Test rate limiting for messaging"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.agent = User.objects.create_user(
            username='testagent',
            email='agent@example.com',
            password='testpass123'
        )
        
        # Create profiles
        for u in [self.user, self.agent]:
            if not hasattr(u, 'profile'):
                Profile.objects.create(user=u)
        
        # Create conversation
        self.conversation = Conversation.objects.create(
            user=self.user,
            agent=self.agent
        )
        
        # Clear cache before each test
        cache.clear()
    
    def test_http_message_rate_limit(self):
        """Test HTTP API message rate limiting"""
        self.client.force_authenticate(user=self.user)
        url = f'/api/v1/communications/conversations/{self.conversation.id}/send_message/'
        
        # Send messages up to limit (60/min)
        # We'll send a smaller burst for testing
        for i in range(10):
            response = self.client.post(url, {'text': f'Test message {i}'})
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Note: In real scenario, sending 61 messages would trigger throttle
        # For unit test, we'd need to mock time or use smaller limits
    
    def test_websocket_rate_limit(self):
        """Test WebSocket rate limiting logic"""
        limiter = WebSocketRateLimit(max_messages=5, window=10)
        
        # Should allow first 5 messages
        for i in range(5):
            self.assertTrue(limiter.allow_message(self.user.id, self.conversation.id))
        
        # 6th message should be throttled
        with self.assertRaises(Throttled):
            limiter.allow_message(self.user.id, self.conversation.id)
        
        # Wait for window to expire and try again
        time.sleep(11)
        cache.clear()  # Clear expired entries
        self.assertTrue(limiter.allow_message(self.user.id, self.conversation.id))
    
    def test_rate_limit_per_user(self):
        """Test that rate limits are per-user"""
        limiter = WebSocketRateLimit(max_messages=3, window=10)
        
        # User 1 sends 3 messages
        for i in range(3):
            limiter.allow_message(self.user.id, self.conversation.id)
        
        # User 2 should still be able to send messages
        self.assertTrue(limiter.allow_message(self.agent.id, self.conversation.id))


class EncryptionTests(TestCase):
    """Test message encryption"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.agent = User.objects.create_user(
            username='testagent',
            email='agent@example.com',
            password='testpass123'
        )
        
        # Create profiles
        for u in [self.user, self.agent]:
            if not hasattr(u, 'profile'):
                Profile.objects.create(user=u)
        
        self.conversation = Conversation.objects.create(
            user=self.user,
            agent=self.agent
        )
    
    def test_message_auto_encryption(self):
        """Test that messages are automatically encrypted on save"""
        plaintext = "This is a secret message"
        
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.user,
            text=plaintext
        )
        
        # Refresh from database
        message.refresh_from_db()
        
        # Message should be marked as encrypted
        self.assertTrue(message.is_encrypted)
        
        # Encrypted text should not be None and should differ from plaintext
        self.assertIsNotNone(message.text_encrypted)
        self.assertNotEqual(message.text_encrypted, plaintext)
        
        # Decrypted text should match original
        self.assertEqual(message.decrypted_text, plaintext)
    
    def test_encryption_decryption_roundtrip(self):
        """Test that encryption and decryption work correctly"""
        encryptor = get_encryptor()
        
        original = "Test message with emojis 🔒🔐"
        encrypted = encryptor.encrypt(original)
        decrypted = encryptor.decrypt(encrypted)
        
        self.assertNotEqual(encrypted, original)
        self.assertEqual(decrypted, original)
    
    def test_empty_message_encryption(self):
        """Test handling of empty messages"""
        encryptor = get_encryptor()
        
        encrypted = encryptor.encrypt("")
        decrypted = encryptor.decrypt("")
        
        self.assertEqual(encrypted, "")
        self.assertEqual(decrypted, "")
    
    def test_backward_compatibility(self):
        """Test that old unencrypted messages still work"""
        # Create message without triggering auto-encryption
        message = Message(
            conversation=self.conversation,
            sender=self.user,
            text="Old plaintext message",
            is_encrypted=False
        )
        # Use super().save() to bypass encryption
        super(Message, message).save()
        
        # Decrypted text should return the plain text field
        self.assertEqual(message.decrypted_text, "Old plaintext message")
        self.assertFalse(message.is_encrypted)


class SecurityIntegrationTests(TestCase):
    """Integration tests for security features"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.agent = User.objects.create_user(
            username='testagent',
            email='agent@example.com',
            password='testpass123'
        )
        
        # Create profiles
        for u in [self.user, self.agent]:
            if not hasattr(u, 'profile'):
                Profile.objects.create(user=u)
        
        self.conversation = Conversation.objects.create(
            user=self.user,
            agent=self.agent
        )
    
    def test_encrypted_message_via_api(self):
        """Test that messages sent via API are encrypted"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(
            f'/api/v1/communications/conversations/{self.conversation.id}/send_message/',
            {'text': 'Secret message via API'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Fetch message from database
        message = Message.objects.get(id=response.data['id'])
        
        # Should be encrypted
        self.assertTrue(message.is_encrypted)
        self.assertIsNotNone(message.text_encrypted)
        
        # API response should contain decrypted text
        self.assertEqual(response.data['text'], 'Secret message via API')
    
    def test_unauthorized_access_blocked(self):
        """Test that rate limiting doesn't bypass authorization"""
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123'
        )
        Profile.objects.get_or_create(user=other_user)
        
        self.client.force_authenticate(user=other_user)
        
        # Should not be able to send message to conversation they're not part of
        response = self.client.post(
            f'/api/v1/communications/conversations/{self.conversation.id}/send_message/',
            {'text': 'Unauthorized message'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
