"""
WebSocket consumer for live match updates.

Clients connect to ws://<host>/ws/match/<match_id>/
to receive real-time updates about a match (score changes, status changes, etc.).
"""

import json
import logging
import re

from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Match

logger = logging.getLogger(__name__)


class MatchUpdateConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer that pushes live match updates to connected clients.

    Room name pattern: match_<match_id>
    """

    async def connect(self):
        # Extract match_id from scope - works with both URLRouter and direct testing
        match_id = None
        url_route = self.scope.get("url_route")

        if url_route and "kwargs" in url_route:
            match_id = url_route["kwargs"].get("match_id")

        # Fallback: try to extract from path
        if match_id is None:
            path = self.scope.get("path", "")
            match = re.search(r"/ws/match/(\d+)/", path)
            if match:
                match_id = match.group(1)

        if not match_id:
            await self.close(code=4000)
            return

        self.match_id = match_id
        self.room_group_name = f"match_{self.match_id}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

        # Send initial match data on connection
        try:
            match = await self._get_match_data(self.match_id)
            if match:
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "match_update",
                            "action": "initial",
                            "data": match,
                        }
                    )
                )
        except Exception as e:
            logger.error(f"Error sending initial match data: {e}")

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )

    async def receive(self, text_data):
        """
        Handle incoming messages from WebSocket.
        Currently, clients are read-only (only receive updates).
        A ping/pong mechanism can be added for keep-alive.
        """
        try:
            data = json.loads(text_data)
            if data.get("type") == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
        except json.JSONDecodeError:
            pass

    async def match_update(self, event):
        """
        Receive a match update from the channel layer and forward to WebSocket.
        Called by channel_layer.group_send from external code (e.g., views).
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "match_update",
                    "action": event.get("action", "update"),
                    "data": event.get("data", {}),
                }
            )
        )

    async def _get_match_data(self, match_id):
        """
        Fetch match data from the database asynchronously.
        Uses sync_to_async for Django ORM calls.
        """
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def get_match():
            try:
                match = Match.objects.select_related(
                    "competition", "home_club", "away_club"
                ).get(id=match_id)
                from .serializers import MatchDetailSerializer

                return MatchDetailSerializer(match).data
            except Match.DoesNotExist:
                return None

        return await get_match()
