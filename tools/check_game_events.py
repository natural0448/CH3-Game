import json
from pathlib import Path

path = Path("../data-replay/raw/game-events.jsonl")
with path.open(encoding="utf-8") as source:
    event = next(
        (json.loads(line) for line in source if line.strip()), None
    )
if event is None:
    print("입력이 비어 있습니다. 집계 수는 0입니다.")
else:
    required = {
        "event_id", "event_type", "player_id",
        "room_id", "event_time", "payload",
    }
    print({
        "missing": sorted(required - event.keys()),
        "event_id": event["event_id"],
        "event_type": event["event_type"],
        "payload_fields": sorted(event["payload"]),
    })