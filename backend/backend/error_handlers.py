from django.http import JsonResponse
from django.utils import timezone
import uuid
import logging

logger = logging.getLogger(__name__)

def make_error_response(message, code, status_code, details=None):
    """Helper to create consistent JSON error responses."""
    request_id = str(uuid.uuid4())
    logger.error(f"Error {status_code}: {message} [Request ID: {request_id}]")
    
    response_data = {
        'error': message,
        'code': code,
        'status': status_code,
        'timestamp': timezone.now().isoformat(),
        'request_id': request_id
    }
    
    if details:
        response_data['details'] = details
        
    return JsonResponse(response_data, status=status_code)

def handler404(request, exception=None):
    """
    Custom 404 error handler.
    Always return JSON for API requests or if Accept header prefers JSON.
    """
    if request.path.startswith('/api/') or 'application/json' in request.headers.get('Accept', ''):
        return make_error_response("The requested resource was not found.", "NOT_FOUND", 404)
    
    # For regular browser requests (admin, etc.), let Django handle it normally (or generic HTML)
    # But since this is primarily an API backend for SPA, JSON is usually safer.
    # However, if using Django Admin, we might want HTML.
    # Simple check:
    if request.path.startswith('/admin/'):
         # We can't easily fallback to default from here without importing default view
         # So we will just return a simple HTML response or let Django defaults work if we don't set this handler
         # But we ARE setting this handler.
         # For simplicity in this specialized backend, good textual message is fine.
         from django.views.defaults import page_not_found
         return page_not_found(request, exception)

    return make_error_response("Page not found.", "NOT_FOUND", 404)

def handler500(request):
    """
    Custom 500 error handler.
    """
    if request.path.startswith('/api/') or 'application/json' in request.headers.get('Accept', ''):
         return make_error_response("Internal Server Error. Our team has been notified.", "INTERNAL_ERROR", 500)
    
    from django.views.defaults import server_error
    return server_error(request)

def handler403(request, exception=None):
    """
    Custom 403 error handler.
    """
    if request.path.startswith('/api/'):
        return make_error_response("You do not have permission to perform this action.", "PERMISSION_DENIED", 403)
    
    from django.views.defaults import permission_denied
    return permission_denied(request, exception)

def handler400(request, exception=None):
    """
    Custom 400 error handler.
    """
    if request.path.startswith('/api/'):
         return make_error_response("Bad Request.", "BAD_REQUEST", 400)

    from django.views.defaults import bad_request
    return bad_request(request, exception)
