import time
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from game.models import Player
from game.services import serialize_player, apply_command

@database_sync_to_async
def read_player(user_id):
    return serialize_player(Player.objects.get(user_id=user_id))

run_command = database_sync_to_async(apply_command)

class PlayConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close(code=4401)
            return
        self.last_action = 0.0
        await self.accept()
        await self.send_json(await read_player(self.user.pk))

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
        await self.send_json(state)        