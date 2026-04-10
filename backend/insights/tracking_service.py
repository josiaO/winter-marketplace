"""
Centralized event tracking service for analytics.
Handles event logging, device detection, and metadata enrichment.
"""
from typing import Optional, Dict, Any
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Event
import user_agents

User = get_user_model()


class TrackingService:
    """Service for tracking user events and behavioral analytics."""
    
    @staticmethod
    def get_device_type(user_agent_string: str) -> str:
        """Parse user agent to determine device type."""
        if not user_agent_string:
            return 'unknown'
        
        ua = user_agents.parse(user_agent_string)
        
        if ua.is_mobile:
            return 'mobile'
        elif ua.is_tablet:
            return 'tablet'
        elif ua.is_pc:
            return 'desktop'
        else:
            return 'other'
    
    @staticmethod
    def track_event(
        session_id: str,
        event_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        user: Optional[User] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        referrer: Optional[str] = None
    ) -> Event:
        """
        Track a user event with comprehensive metadata.
        
        Args:
            session_id: Session identifier (for anonymous users)
            event_type: Type of event (e.g., 'page_view', 'listing_search')
            metadata: Additional event-specific data
            user: Authenticated user (if applicable)
            ip_address: Client IP address
            user_agent: Client user agent string
            referrer: HTTP referrer
            
        Returns:
            Created Event instance
        """
        # Determine device type
        device_type = TrackingService.get_device_type(user_agent or '')
        
        # Create event
        event = Event.objects.create(
            session_id=session_id,
            user=user,
            event_type=event_type,
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type,
            referrer=referrer
        )
        
        return event
    
    @staticmethod
    def track_from_request(request, event_type: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Convenience method to track event from Django request object.
        
        Args:
            request: Django HttpRequest object
            event_type: Type of event
            metadata: Additional event metadata
        """
        # Get or create session
        if not request.session.session_key:
            request.session.create()
        
        session_id = request.session.session_key
        user = request.user if request.user.is_authenticated else None
        ip_address = TrackingService._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        referrer = request.META.get('HTTP_REFERER', '')
        
        return TrackingService.track_event(
            session_id=session_id,
            event_type=event_type,
            metadata=metadata,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            referrer=referrer
        )
    
    @staticmethod
    def _get_client_ip(request) -> str:
        """Extract client IP from request, handling proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
