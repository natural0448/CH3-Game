from uuid import UUID
from django.db import transaction
from django.utils import timezone
from game.models import Player, GameEvent

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
WIDTH, HEIGHT = 20, 15
GATHER_TILE = (2, 2)


def serialize_player(player):
    return {
        "player_id": player.pk,
        "type": "state",
        "room_id": player.room_id,
        "x": player.x,
        "y": player.y,
        "coins": player.coins,
        "version": player.version,
    }

@transaction.atomic
def apply_command(user_id, command):
    command_id = str(UUID(str(command["command_id"])))
    action = command.get("type")
    player = Player.objects.select_for_update().get(user_id=user_id)
    previous = GameEvent.objects.filter(
        player=player, payload__command_id=command_id
    ).first()
    if previous is not None:
        state = serialize_player(player)
        state["command_id"] = command_id
        return state
    if action == "move":
        direction = command.get("direction")
        if direction not in DIRECTIONS:
            raise ValueError("invalid_direction")
        dx, dy = DIRECTIONS[direction]
        next_x, next_y = player.x + dx, player.y + dy
        if not (0 <= next_x < WIDTH and 0 <= next_y < HEIGHT):
            raise ValueError("outside_map")
        player.x, player.y = next_x, next_y
        event_type = "player.moved"
    elif action == "gather":
        if (player.x, player.y) != GATHER_TILE:
            raise ValueError("not_at_gather_tile")
        player.coins += 1
        event_type = "player.gathered"
    else:
        raise ValueError("unknown_action")

    player.version += 1
    player.save(update_fields=["x", "y", "coins", "version", "updated_at"])
    state = serialize_player(player)
    GameEvent.objects.create(
        event_type=event_type,
        player=player,
        room_id=player.room_id,
        event_time=timezone.now(),
        payload={"command_id": command_id, "x": player.x, "y": player.y,
                 "coins": player.coins, "version": player.version},
    )
    state["command_id"] = command_id
    return state