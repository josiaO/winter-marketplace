from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
import logging

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    """
    Custom exception handler for Django REST Framework.
    """
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    # If response is None, then there's an unhandled exception
    if response is None:
        import traceback
        try:
            with open("/tmp/django_500.txt", "w") as f:
                f.write(traceback.format_exc())
            logger.error("Wrote traceback to /tmp/django_500.txt")
        except Exception as e:
            logger.error(f"Failed to write traceback to /tmp: {e}")
        User = get_user_model()
        
        # Handle User.DoesNotExist specifically for SimpleJWT token refresh
        # This happens when a token contains a user_id that no longer exists
        if isinstance(exc, (User.DoesNotExist, ObjectDoesNotExist)) and 'TokenRefresh' in str(type(context.get('view'))):
            logger.warning(f"User not found during token refresh: {exc}")
            return Response(
                {'error': 'User not found', 'code': 'user_not_found'},
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        # Catch other user lookup failures in auth views
        if isinstance(exc, User.DoesNotExist):
             logger.warning(f"User not found in API view {context.get('view')}: {exc}")
             return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    return response
