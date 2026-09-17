from uuid import UUID, uuid4
from django.db import transaction
from django.utils import timezone
from game.models import Player, GameEvent

DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
WIDTH, HEIGHT = 20, 15
GATHER_TILE = (2, 2)
TRAIN_TILE = (3, 2)
EPISODE_STEPS = 5

def observe_player(player):
    return {
        "x": player.x,
        "y": player.y,
        "coins": player.coins,
    }


def serialize_player(player):
    return {
        "player_id": player.pk,
        "username": player.user.username,
        "type": "state",
        "room_id": player.room_id,
        "x": player.x,
        "y": player.y,
        "coins": player.coins,
        "version": player.version,
    }

def next_transition_position(player):
    last_event = GameEvent.objects.filter(
        player=player
    ).order_by("-event_time", "-event_id").first()
    previous = (
        last_event.payload.get("transition")
        if last_event is not None else None
    )
    if previous and not previous.get("done", False):
        return previous["episode_id"], int(previous["step"]) + 1
    return str(uuid4()), 1


@transaction.atomic
def apply_command(user_id, command):
    command_id = str(UUID(str(command["command_id"])))
    action = command.get("type")
    player = Player.objects.select_for_update().get(user_id=user_id)
    duplicate = GameEvent.objects.filter(
        player=player, payload__command_id=command_id
    ).first()

    if duplicate is not None:
        state = serialize_player(player)
        state["command_id"] = command_id
        return state

    before = observe_player(player)
    episode_id, step = next_transition_position(player)
    action_record = {"type": action}

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
        action_record["direction"] = direction

    elif action == "gather":
        if (player.x, player.y) != GATHER_TILE:
            raise ValueError("not_at_gather_tile")
        player.coins += 1
        event_type = "player.gathered"

    elif action == "train":
        if (player.x, player.y) != TRAIN_TILE:
            raise ValueError("not_at_train_tile")
        player.coins += 1
        event_type = "player.trained"

    else:
        raise ValueError("unknown_action")

    player.version += 1
    player.save(update_fields=[
        "x", "y", "coins", "version", "updated_at"
    ])
    after = observe_player(player)
    truncated = step == EPISODE_STEPS
    transition = {
        "episode_id": episode_id,
        "step": step,
        "observation": before,
        "action": action_record,
        "reward": after["coins"] - before["coins"],
        "next_observation": after,
        "done": truncated,
        "terminated": False,
        "truncated": truncated,
        "policy_version": "manual-v1",
    }
    GameEvent.objects.create(
        event_type=event_type,
        player=player,
        room_id=player.room_id,
        event_time=timezone.now(),
        payload={
            "command_id": command_id,
            "x": player.x,
            "y": player.y,
            "coins": player.coins,
            "version": player.version,
            "transition": transition,
        },
    )
    state = serialize_player(player)
    state["command_id"] = command_id
    return state

def serialize_event(event):
    """Preserve the identity and occurrence time of an already committed fact."""
    return {
        "schema_version": 1,
        "event_id": str(event.event_id),
        "event_type": event.event_type,
        "player_id": event.player_id,
        "room_id": event.room_id,
        "event_time": event.event_time.isoformat(),
        "payload": event.payload,
    }

