r"""14일차 1교시 4~5번: 지정 계정의 실제 수련 한 건을 읽는다.

Game-server에서 실행:
    .\server\.venv\Scripts\python.exe .\tools\inspect_training_event.py --username python
DB는 계정의 player_id 조회에만 사용하고, 이벤트는 기존 export 파일에서 읽는다.
원본 수정, 새 행동 실행, Kafka 발행은 하지 않는다.
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="계정별 최신 수련 원본과 두 UUID 확인")
    parser.add_argument("--username", default="python")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "server"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    django.setup()
    from django.conf import settings
    from game.models import Player

    player_id = Player.objects.filter(user__username=args.username).values_list("pk", flat=True).first()
    if player_id is None:
        parser.exit(1, "해당 계정의 게임 캐릭터가 없습니다. 아이디를 확인하세요.\n")
    source = settings.DATA_DIR / "raw" / "game-events.jsonl"
    if not source.exists():
        parser.exit(1, "원본 파일이 없습니다. manage.py export_game_events를 먼저 실행하세요.\n")

    latest = None
    latest_key = None
    with source.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event["event_type"] != "player.trained" or event["player_id"] != player_id:
                    continue
                key = (datetime.fromisoformat(event["event_time"]), event["event_id"])
                if latest_key is None or key > latest_key:
                    latest, latest_key = event, key
            except (ValueError, KeyError, TypeError) as exc:
                parser.exit(1, f"원본 {line_number}행 형식을 확인하세요 ({type(exc).__name__}).\n")

    if latest is None:
        parser.exit(1, "이 계정의 수련 기록이 export에 없습니다. (3, 2)에서 X키로 수련 후 export_game_events를 실행하세요.\n")
    print("[4] latest: " + str(source))
    print(json.dumps(latest, ensure_ascii=False, indent=2))
    print("[5] event_id / command_id")
    print(json.dumps({
        "event_id": latest["event_id"],
        "command_id": latest["payload"]["command_id"],
        "player_id": latest["player_id"],
        "room_id": latest["room_id"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
