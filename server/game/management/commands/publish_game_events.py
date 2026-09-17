"""One publisher process: MySQL outbox -> Kafka ack -> published_at.

An exit between ack and the DB update can redeliver the SAME event_id.
Downstream analysis must deduplicate by event_id. This is not exactly-once.
"""
import json
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from kafka import KafkaProducer
from kafka.errors import KafkaError

from game.models import GameEvent
from game.services import serialize_event


class Command(BaseCommand):
    help = "확정된 미발행 이벤트를 Kafka에 전달합니다. publisher는 한 프로세스만 실행하세요."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="미발행 묶음 한 번만 처리하고 종료")
        parser.add_argument("--batch-size", type=int, default=50)

    def handle(self, *args, **options):
        if options["batch_size"] < 1:
            raise CommandError("batch-size는 1 이상이어야 합니다.")
        producer = None
        count = 0
        try:
            producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                acks="all",
                enable_idempotence=True,
                max_block_ms=10000,
                key_serializer=lambda value: str(value).encode("utf-8"),
                value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
            )
            while True:
                rows = list(GameEvent.objects.filter(published_at__isnull=True)
                            .order_by("event_time", "event_id")[:options["batch_size"]])
                for event in rows:
                    metadata = producer.send(
                        settings.KAFKA_EVENT_TOPIC, key=event.player_id,
                        value=serialize_event(event),
                    ).get(timeout=10)
                    GameEvent.objects.filter(event_id=event.event_id, published_at__isnull=True).update(
                        published_at=timezone.now()
                    )
                    count += 1
                    self.stdout.write(
                        f"event={event.event_id} key={event.player_id} "
                        f"partition={metadata.partition} offset={metadata.offset}"
                    )
                if options["once"]:
                    break
                if not rows:
                    time.sleep(0.5)
        except KeyboardInterrupt:
            self.stdout.write("publisher를 정상 종료합니다.")
        except KafkaError as exc:
            raise CommandError(
                f"Kafka 발행 확인 실패 ({type(exc).__name__}). 미확인 이벤트는 미발행으로 유지됩니다."
            ) from None
        finally:
            if producer is not None:
                producer.close(timeout=10)
        self.stdout.write(f"published={count}")
