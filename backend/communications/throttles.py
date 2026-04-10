from rest_framework.throttling import UserRateThrottle
from django.core.cache import cache
from rest_framework.exceptions import Throttled
import time
import logging

logger = logging.getLogger(__name__)


class MessageRateThrottle(UserRateThrottle):
    """Throttle for sending messages via HTTP API"""
    scope = 'messages'
    rate = '60/min'


class ConversationRateThrottle(UserRateThrottle):
    """Throttle for creating conversations"""
    scope = 'conversations'
    rate = '20/hour'


class WebSocketRateLimit:
    """Rate limiter for WebSocket messages"""
    
    def __init__(self, max_messages=10, window=10):
        """
        Initialize rate limiter
        
        Args:
            max_messages: Maximum messages allowed in window
            window: Time window in seconds
        """
        self.max_messages = max_messages
        self.window = window
    
    def allow_message(self, user_id, conversation_id):
        """
        Check if user can send message
        
        Args:
            user_id: User ID
            conversation_id: Conversation ID
            
        Returns:
            True if allowed
            
        Raises:
            Throttled: If rate limit exceeded
        """
        key = f"ws_rate:{user_id}:{conversation_id}"
        now = time.time()
        
        # Get recent messages
        messages = cache.get(key, [])
        
        # Remove old messages outside window
        messages = [t for t in messages if now - t < self.window]
        
        # Check limit
        if len(messages) >= self.max_messages:
            wait_time = int(self.window - (now - messages[0]))
            logger.warning(f"Rate limit exceeded for user {user_id} in conversation {conversation_id}")
            raise Throttled(wait=wait_time, detail=f"Rate limit exceeded. Please wait {wait_time} seconds.")
        
        # Add current message
        messages.append(now)
        cache.set(key, messages, self.window + 5)
        
        return True
