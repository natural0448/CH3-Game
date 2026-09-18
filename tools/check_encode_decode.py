import json
import os
import sys
from pathlib import Path

import django

# tools 파일을 직접 실행할 때도 config와 game을 찾도록 경로를 추가한다.
# 현재 터미널 위치가 아니라 이 파일의 위치를 기준으로 계산한다.
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "server"))

# manage.py shell 밖에서는 Django 설정을 직접 초기화해야 한다.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings
from game.transforms import parse_game_event


path = settings.DATA_DIR / "raw" / "game-events.jsonl"
with path.open("rb") as stream:
    raw_line = next(
        (line for line in stream if line.strip()), None
    )
if raw_line is None:
    print("원본 파일이 비어 있습니다.")
else:
    parsed = parse_game_event(raw_line)
    print({
        "event_id": parsed["event_id"],
        "event_type": parsed["event_type"],
        "player_id": parsed["player_id"],
        "payload_fields": sorted(parsed["payload"]),
    })

if raw_line is not None:
    encoded = json.dumps(
        parsed, ensure_ascii=False
    ).encode("utf-8")
    restored = parse_game_event(encoded)
    print({
        "same_event_id": parsed["event_id"] == restored["event_id"],
        "same_payload": parsed["payload"] == restored["payload"],
        "same_event_time": parsed["event_time"] == restored["event_time"],
    })
