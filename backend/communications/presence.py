"""
Redis-based presence system for real-time user online/offline tracking.

This module provides WhatsApp-style presence management with automatic TTL expiration,
heartbeat support, and efficient online status lookups.

Key Features:
- User presence with 60s TTL (auto-expires if connection lost)
- Heartbeat mechanism to keep presence alive
- Fast Redis lookups (sub-millisecond)
- No database writes for connection/disconnection
"""

import logging
from typing import List, Optional
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Redis key patterns
PRESENCE_KEY_PATTERN = "presence:user:{user_id}"
PRESENCE_TTL = 60  # seconds


class PresenceManager:
    """Manage user online/offline presence using Redis with TTL."""
    
    @staticmethod
    def _get_key(user_id: int) -> str:
        """Generate Redis key for user presence."""
        return PRESENCE_KEY_PATTERN.format(user_id=user_id)
    
    @staticmethod
    def set_online(user_id: int, ttl: int = PRESENCE_TTL) -> bool:
        """
        Mark user as online with TTL.
        
        Args:
            user_id: User ID to mark online
            ttl: Time-to-live in seconds (default: 60s)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = PresenceManager._get_key(user_id)
            cache.set(key, "1", timeout=ttl)
            logger.debug(f"User {user_id} marked online (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Failed to set user {user_id} online: {e}")
            return False
    
    @staticmethod
    def set_offline(user_id: int) -> bool:
        """
        Mark user as offline immediately.
        
        Args:
            user_id: User ID to mark offline
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = PresenceManager._get_key(user_id)
            cache.delete(key)
            logger.debug(f"User {user_id} marked offline")
            return True
        except Exception as e:
            logger.error(f"Failed to set user {user_id} offline: {e}")
            return False
    
    @staticmethod
    def is_online(user_id: int) -> bool:
        """
        Check if user is currently online.
        
        Args:
            user_id: User ID to check
            
        Returns:
            True if online, False if offline or key expired
        """
        try:
            key = PresenceManager._get_key(user_id)
            value = cache.get(key)
            return value is not None
        except Exception as e:
            logger.error(f"Failed to check presence for user {user_id}: {e}")
            return False
    
    @staticmethod
    def refresh_presence(user_id: int, ttl: int = PRESENCE_TTL) -> bool:
        """
        Refresh user presence (heartbeat).
        
        This should be called periodically (e.g., every 30s) from the client
        to keep the user's online status active.
        
        Args:
            user_id: User ID to refresh
            ttl: New TTL in seconds
            
        Returns:
            True if successful, False otherwise
        """
        return PresenceManager.set_online(user_id, ttl)
    
    @staticmethod
    def get_online_users(user_ids: List[int]) -> List[int]:
        """
        Check presence for multiple users at once (batch operation).
        
        Optimized to use Redis MGET for a single network round-trip
        instead of N individual calls.
        
        Args:
            user_ids: List of user IDs to check
            
        Returns:
            List of user IDs that are currently online
        """
        if not user_ids:
            return []
        
        try:
            # Generate all Redis keys
            keys = [PresenceManager._get_key(user_id) for user_id in user_ids]
            
            # Use MGET for batch retrieval (single network round-trip)
            # Access raw Redis client if using django-redis
            if hasattr(cache, 'client'):
                redis_client = cache.client.get_client()
                values = redis_client.mget(keys)
            else:
                # Fallback to individual calls if MGET not available
                values = [cache.get(key) for key in keys]
            
            # Filter online users (where value is not None)
            online_users = [
                user_id for user_id, value in zip(user_ids, values)
                if value is not None
            ]
            
            logger.debug(f"Batch presence check: {len(online_users)}/{len(user_ids)} users online")
            return online_users
            
        except Exception as e:
            logger.error(f"Failed to batch check presence: {e}")
            # Fallback to individual checks on error
            online_users = []
            for user_id in user_ids:
                if PresenceManager.is_online(user_id):
                    online_users.append(user_id)
            return online_users
    
    @staticmethod
    def get_ttl(user_id: int) -> Optional[int]:
        """
        Get remaining TTL for user's presence.
        
        Args:
            user_id: User ID to check
            
        Returns:
            Remaining seconds, or None if offline/expired
        """
        try:
            key = PresenceManager._get_key(user_id)
            # Django cache doesn't expose TTL directly, so we return None
            # if using django-redis, you can access the raw Redis client:
            if hasattr(cache, 'client'):
                redis_client = cache.client.get_client()
                ttl = redis_client.ttl(key)
                return ttl if ttl > 0 else None
            return None
        except Exception as e:
            logger.error(f"Failed to get TTL for user {user_id}: {e}")
            return None


# Convenience functions for backward compatibility
def set_user_online(user_id: int) -> bool:
    """Mark user as online (convenience wrapper)."""
    return PresenceManager.set_online(user_id)


def set_user_offline(user_id: int) -> bool:
    """Mark user as offline (convenience wrapper)."""
    return PresenceManager.set_offline(user_id)


def is_user_online(user_id: int) -> bool:
    """Check if user is online (convenience wrapper)."""
    return PresenceManager.is_online(user_id)


def refresh_user_presence(user_id: int) -> bool:
    """Refresh user presence heartbeat (convenience wrapper)."""
    return PresenceManager.refresh_presence(user_id)
