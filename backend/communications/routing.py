from django.urls import re_path
from . import consumers
from commerce import consumers as commerce_consumers

websocket_urlpatterns = [
    re_path(r'ws/notifications/?$', consumers.NotificationConsumer.as_asgi()),
    re_path(
        r'ws/chat/(?P<conversation_id>\d+)/?$',
        consumers.ChatConsumer.as_asgi(),
    ),
    re_path(
        r'ws/dashboard/?$',
        commerce_consumers.DashboardConsumer.as_asgi(),
    )
]
