import logging
from celery import shared_task
from django.utils import timezone
from .models import Visitor, Event
from .tracking_service import TrackingService

logger = logging.getLogger(__name__)

@shared_task(name='insights.tasks.track_visitor_event_task')
def track_visitor_event_task(session_key, ip_address, user_agent, path, method, event_type='page_view', metadata=None):
    """
    Asynchronously persist visitor tracking data and events.
    This offloads database writes from the main request/response cycle.
    """
    try:
        # 1. Update or create Visitor record
        visitor, created = Visitor.objects.get_or_create(
            session_key=session_key,
            defaults={
                "ip_address": ip_address,
                "user_agent": user_agent
            }
        )

        if not created:
            visitor.visit_count += 1
            visitor.last_seen = timezone.now()
            visitor.save(update_fields=["visit_count", "last_seen"])
        
        # 2. Persist the specific event if needed
        if event_type:
            # Note: We use the session_key as session_id in the Event model
            # as per current implementation patterns.
            Event.objects.create(
                session_id=session_key,
                event_type=event_type,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=metadata or {},
                created_at=timezone.now()
            )
            
    except Exception as e:
        logger.error(f"Error in track_visitor_event_task: {e}", exc_info=True)
