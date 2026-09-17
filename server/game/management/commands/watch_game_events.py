"""Read-only observation. Commit only after every record in a poll is printed."""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from kafka import KafkaConsumer
from kafka.errors import KafkaError


class Command(BaseCommand):
    help = "게임 상태를 바꾸지 않고 Kafka 확정 사실과 partition/offset을 읽습니다."

    def add_arguments(self, parser):
        parser.add_argument("--group", default=settings.KAFKA_GROUP_ID)
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        if options["limit"] < 1 or not options["group"].strip():
            raise CommandError("limit는 1 이상, group은 비어 있지 않아야 합니다.")
        consumer = None
        count = 0
        try:
            consumer = KafkaConsumer(
                settings.KAFKA_EVENT_TOPIC,
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                group_id=options["group"], auto_offset_reset="earliest",
                enable_auto_commit=False, consumer_timeout_ms=5000,
                key_deserializer=lambda value: value.decode("utf-8") if value is not None else None,
                value_deserializer=lambda value: json.loads(value.decode("utf-8")),
            )
            while count < options["limit"]:
                batches = consumer.poll(timeout_ms=2000, max_records=options["limit"] - count)
                if not batches:
                    break
                for records in batches.values():
                    for record in records:
                        event = record.value
                        self.stdout.write(json.dumps({
                            "event_id": event["event_id"], "event_type": event["event_type"],
                            "player_id": event["player_id"], "room_id": event["room_id"],
                            "key": record.key, "topic": record.topic,
                            "partition": record.partition, "offset": record.offset,
                        }, ensure_ascii=False))
                        count += 1
                consumer.commit()
        except KeyboardInterrupt:
            self.stdout.write("관찰을 마칩니다.")
        except (KafkaError, ValueError, KeyError, TypeError, UnicodeError) as exc:
            raise CommandError(
                f"Kafka 관찰 실패 ({type(exc).__name__}). 완료하지 못한 묶음은 commit하지 않았습니다."
            ) from None
        finally:
            if consumer is not None:
                consumer.close(autocommit=False)
        self.stdout.write(f"observed={count}")
