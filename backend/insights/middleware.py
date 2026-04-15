from .tasks import track_visitor_event_task

class VisitorTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Capture metadata from the request before response processing
        path = request.path
        should_track = not any([
            path.startswith('/admin'),
            path.startswith('/static'),
            path.startswith('/media'),
            path.startswith('/api/v1/insights/track'),
        ])
        
        # Use existing session key if available, but do not force creation
        # to avoid recursive writes and infinite loops with instrumentation.
        session_key = getattr(request.session, 'session_key', None)
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")

        # 2. Dispatch to Celery task for async persistence
        # Only track if we have a valid session key to avoid IntegrityErrors in workers.
        if should_track and session_key:
            try:
                track_visitor_event_task.delay(
                    session_key=session_key,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    path=path,
                    method=request.method,
                    event_type='page_view',
                    metadata={'path': path, 'method': request.method}
                )
            except Exception:
                # Silently fail analytics capture to maintain site availability
                pass

        return self.get_response(request)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return request.META.get("REMOTE_ADDR")
