from .models import Visitor
from .tracking_service import TrackingService

class VisitorTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip tracking for admin, static, media, and API endpoints (except listing views)
        path = request.path
        should_track_pageview = not any([
            path.startswith('/admin'),
            path.startswith('/static'),
            path.startswith('/media'),
            path.startswith('/api/v1/insights/track'),  # Don't double-track
        ])
        
        if not request.session.session_key:
            request.session.create()

        session_key = request.session.session_key

        # Update or create Visitor record (for backward compatibility)
        visitor, created = Visitor.objects.get_or_create(
            session_key=session_key,
            defaults={
                "ip_address": self.get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", "")
            }
        )

        if not created:
            visitor.visit_count += 1
            visitor.save(update_fields=["visit_count", "last_seen"])
        
        # Track page_view event for analytics
        if should_track_pageview:
            TrackingService.track_from_request(
                request=request,
                event_type='page_view',
                metadata={'path': path, 'method': request.method}
            )

        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR")
