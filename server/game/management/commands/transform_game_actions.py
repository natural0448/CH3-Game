import json
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from kafka import KafkaConsumer, KafkaProducer, TopicPartition
from kafka.structs import OffsetAndMetadata
from game.transforms import parse_game_event, is_game_action, with_action_label


class Command(BaseCommand):
    help = "확정 게임 사실을 Python으로 필터·변환해 행동 Topic에 발행"

    def add_arguments(self, parser):
        parser.add_argument("--group", default="village-actions-v1")
        parser.add_argument("--output-topic", default="game.actions.v1")
        parser.add_argument("--max-events", type=int, default=0)

    def handle(self, *args, **options):
        input_topic = settings.KAFKA_EVENT_TOPIC
        output_topic = options["output_topic"]
        group = options["group"]
        limit = options["max_events"]
        if input_topic == output_topic:
            raise CommandError("입력과 출력 Topic은 분리합니다.")
        if limit < 0:
            raise CommandError("--max-events는 0 이상입니다.")
        if group != "village-actions-v1":
            raise CommandError("정본 group village-actions-v1을 사용합니다.")

        consumer = KafkaConsumer(
            input_topic,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=group,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            max_poll_records=1,
        )
        producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            acks="all",
            enable_idempotence=True,
            value_serializer=lambda value: json.dumps(
                value, ensure_ascii=False
            ).encode("utf-8"),
        )
        read_count = 0
        emitted_count = 0
        filtered_count = 0

        try:
            while limit == 0 or read_count < limit:
                batches = consumer.poll(timeout_ms=1000, max_records=1)
                for topic_partition, records in batches.items():
                    for record in records:
                        event = parse_game_event(record.value)
                        expected_key = str(event["player_id"]).encode("utf-8")
                        if record.key != expected_key:
                            raise CommandError("원본 key와 서버 player_id가 다릅니다.")

                        output_metadata = None
                        if is_game_action(event):
                            transformed = with_action_label(event)
                            output_metadata = producer.send(
                                output_topic,key=record.key,value=transformed,).get(timeout=10)
                            emitted_count += 1
                            outcome = "emitted"
                        else:
                            filtered_count += 1
                            outcome = "filtered"

                        consumer.commit({
                            TopicPartition(
                                record.topic, record.partition
                            ): OffsetAndMetadata(record.offset + 1, "", -1)
                        })
                        read_count += 1
                        self.stdout.write(json.dumps({
                            "outcome": outcome,
                            "event_id": event["event_id"],
                            "player_id": event["player_id"],
                            "input": {
                                "topic": record.topic,
                                "partition": record.partition,
                                "offset": record.offset,
                                "committed_next": record.offset + 1,
                            },
                            "output": (
                                {
                                    "topic": output_metadata.topic,
                                    "partition": output_metadata.partition,
                                    "offset": output_metadata.offset,
                                }
                                if output_metadata is not None else None
                            ),
                        }, ensure_ascii=False))

        except KeyboardInterrupt:
            self.stdout.write("사용자 요청으로 변환기를 종료합니다.")
        finally:
            try:
                producer.flush(timeout=10)
            finally:
                try:
                    producer.close(timeout=10)
                finally:
                    consumer.close(autocommit=False)

        self.stdout.write(json.dumps({
            "group": group,
            "input_topic": input_topic,
            "output_topic": output_topic,
            "read_count": read_count,
            "emitted_count": emitted_count,
            "filtered_count": filtered_count,
        }, ensure_ascii=False))