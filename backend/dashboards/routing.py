"""
WebSocket URL routing for the dashboards app.

Maps WebSocket URL patterns to their consumer handlers.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/match/(?P<match_id>\d+)/$",
        consumers.MatchUpdateConsumer.as_asgi(),
        name="match-live-updates",
    ),
]