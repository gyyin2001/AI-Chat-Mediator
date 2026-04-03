from django.urls import re_path
from . import consumers
websocket_urlpatterns = [
    re_path(r'ws/realtime/(?P<session_id>[-\w]+)/$', consumers.RealtimeRelayConsumer.as_asgi()),
]