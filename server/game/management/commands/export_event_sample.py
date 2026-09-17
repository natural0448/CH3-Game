import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from game.models import GameEvent
from game.services import serialize_event


class Command(BaseCommand):
    help = "상태를 바꾸지 않는 읽기 전용 명령: 최근 확정 이벤트 한 건을 JSON으로 보관합니다."

    def handle(self, *args, **options):
        event = GameEvent.objects.order_by("event_time", "event_id").last()
        if event is None:
            raise CommandError("먼저 마을에서 이동 한 번을 실행하세요.")
        target = settings.DATA_DIR / "samples" / "game-event.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(serialize_event(event), ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(str(target))
