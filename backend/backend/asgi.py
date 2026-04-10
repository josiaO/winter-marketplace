import os

# Ensure settings are set before anything that touches Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

from django.core.asgi import get_asgi_application

# Initialize Django (loads INSTALLED_APPS) before importing app code that uses models
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter

# Import middleware/routing after Django apps are ready
from communications.middleware import JWTAuthMiddleware
import communications.routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter(
            communications.routing.websocket_urlpatterns
        )
    ),
})
