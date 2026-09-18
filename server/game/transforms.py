import json
from datetime import datetime
from uuid import UUID
from copy import deepcopy


REQUIRED_FIELDS = {
    "schema_version",
    "event_id",
    "event_type",
    "player_id",
    "room_id",
    "event_time",
    "payload",
}
ACTION_LABELS = {
    "player.moved": "이동",
    "player.gathered": "개인 채집",
    "player.trained": "개인 수련",
}


def parse_game_event(raw_value):
    if raw_value is None:
        raise ValueError("게임 사실 Topic에는 null value를 넣지 않습니다.")
    event = json.loads(raw_value.decode("utf-8"))
    if not isinstance(event, dict):
        raise ValueError("게임 이벤트의 바깥 구조는 JSON 객체입니다.")
    missing = REQUIRED_FIELDS - event.keys()
    if missing:
        raise ValueError(f"필수 필드 누락: {sorted(missing)}")
    if event["schema_version"] != 1:
        raise ValueError("지원하는 envelope schema_version은 1입니다.")
    UUID(str(event["event_id"]))
    if type(event["player_id"]) is not int:
        raise ValueError("player_id는 서버의 정수 식별자입니다.")
    if not isinstance(event["event_type"], str):
        raise ValueError("event_type은 문자열입니다.")
    if not isinstance(event["room_id"], str):
        raise ValueError("room_id는 문자열입니다.")
    if not isinstance(event["payload"], dict):
        raise ValueError("payload는 JSON 객체입니다.")
    event_time = datetime.fromisoformat(
        event["event_time"].replace("Z", "+00:00")
    )
    if event_time.tzinfo is None:
        raise ValueError("event_time에는 UTC offset이 있어야 합니다.")
    return event

def is_game_action(event):
    return event["event_type"] in ACTION_LABELS

def with_action_label(event):
    if not is_game_action(event):
        raise ValueError("표시 이름을 붙일 게임 행동이 아닙니다.")
    result = deepcopy(event)
    result["payload"]["action_label"] = ACTION_LABELS[event["event_type"]]
    return result

def selected_for_note(event, room_id):
    return is_game_action(event) and event["room_id"] == room_id
