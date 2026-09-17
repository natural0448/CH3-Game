import json

from django.conf import settings
from django.core.management.base import BaseCommand

from game.models import GameEvent
from game.services import serialize_event


class Command(BaseCommand):
    help = "확정 GameEvent를 Spark용 JSONL 스냅샷으로 내보냅니다. JSONL 한 줄은 확정 사실 한 건입니다."

    def handle(self, *args, **options):
        target = settings.DATA_DIR / "raw" / "game-events.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".jsonl.tmp")
        count = 0
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                rows = GameEvent.objects.order_by("event_time", "event_id")
                for event in rows.iterator(chunk_size=500):
                    stream.write(json.dumps(serialize_event(event), ensure_ascii=False) + "\n")
                    count += 1
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        self.stdout.write(f"events={count} path={target}")
