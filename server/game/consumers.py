import time
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from game.models import Player
from game.services import serialize_player, apply_command

@database_sync_to_async
def read_player(user_id):
    return serialize_player(Player.objects.get(user_id=user_id))

run_command = database_sync_to_async(apply_command)

ONLINE = {}

@database_sync_to_async
def read_room(room_id, player_ids):
    players = Player.objects.filter(room_id=room_id, pk__in=player_ids).order_by("id")
    return [serialize_player(player) for player in players]


class PlayConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.player_id = None
        self.group = None
        if not self.user.is_authenticated:
            await self.close(code=4401)
            return
        state = await read_player(self.user.pk)
        player_id = state["player_id"]
        if player_id in ONLINE:
            await self.close(code=4409)
            return
        self.player_id = player_id
        self.room_id = state["room_id"]
        self.group = "room." + self.room_id
        ONLINE[self.player_id] = self.channel_name
        self.last_action = 0.0
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send_json(state)
        await self.channel_layer.group_send(self.group, {"type": "room.snapshot"})

    async def receive_json(self, content, **kwargs):
        command_id = content.get("command_id") if isinstance(content, dict) else None
        if not isinstance(content, dict):
            await self.send_json({"type": "error", "code": "object_required", "command_id": None})
            return
        now = time.monotonic()
        if now - self.last_action < 0.2:
            await self.send_json({"type": "error", "code": "too_fast", "command_id": command_id})
            return
        self.last_action = now
        try:
            state = await run_command(self.user.pk, content)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            await self.send_json({"type": "error", "code": str(exc), "command_id": command_id})
            return
        await self.channel_layer.group_send(self.group, {"type": "room.state", "state": state})


    async def room_snapshot(self, event):
        players = await read_room(self.room_id, list(ONLINE))
        await self.send_json({"type": "snapshot", "players": players})


    async def room_state(self, event):
        await self.send_json(event["state"])


    async def disconnect(self, close_code):
        player_id = getattr(self, "player_id", None)
        group = getattr(self, "group", None)
        if player_id is not None and ONLINE.get(player_id) == self.channel_name:
            ONLINE.pop(player_id, None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)
            await self.channel_layer.group_send(group, {"type": "room.snapshot"})