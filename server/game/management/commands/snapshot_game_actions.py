import json
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from kafka import KafkaConsumer, TopicPartition


class Command(BaseCommand):
    help = "group 위치를 바꾸지 않고 현재 보존 구간을 별도 JSONL로 재읽기"

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)
        parser.add_argument("--max-records", type=int, default=100000)
        parser.add_argument("--timeout-seconds", type=int, default=120)

    def handle(self, *args, **options):
        output = Path(options["output"]).resolve()
        max_records = options["max_records"]
        timeout_seconds = options["timeout_seconds"]
        if not 1 <= max_records <= 1000000:
            raise CommandError("--max-records는 1..1000000입니다.")
        if not 5 <= timeout_seconds <= 600:
            raise CommandError("--timeout-seconds는 5..600입니다.")
        if output.name != "game-events.jsonl":
            raise CommandError("Spark 입력 파일명 game-events.jsonl을 사용합니다.")
        if "data-replay" not in output.parts:
            raise CommandError("독립 data-replay 폴더 아래에 저장합니다.")

        temporary = output.with_suffix(".jsonl.partial")
        manifest_path = output.with_suffix(".manifest.json")
        for candidate in (output, temporary, manifest_path):
            if candidate.exists():
                raise CommandError(f"기존 결과를 보존합니다: {candidate}")
        output.parent.mkdir(parents=True, exist_ok=True)

        consumer = KafkaConsumer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=None,
            enable_auto_commit=False,
            key_deserializer=lambda value: (
                value.decode("utf-8") if value is not None else None
            ),
            value_deserializer=lambda value: json.loads(
                value.decode("utf-8")
            ),
        )
        count = 0
        deadline = time.monotonic() + timeout_seconds

        try:
            topic = "game.actions.v1"
            numbers = consumer.partitions_for_topic(topic)
            if not numbers:
                raise CommandError(f"읽을 Topic이 없습니다: {topic}")
            partitions = [
                TopicPartition(topic, number)
                for number in sorted(numbers)
            ]
            consumer.assign(partitions)
            starts = consumer.beginning_offsets(partitions)
            ends = consumer.end_offsets(partitions)
            for partition in partitions:
                consumer.seek(partition, starts[partition])
            active = {
                partition for partition in partitions
                if starts[partition] < ends[partition]
            }
            if partitions:
                consumer.pause(*[
                    partition for partition in partitions
                    if partition not in active
                ])
            with temporary.open("x", encoding="utf-8") as destination:
                while active:
                    if time.monotonic() >= deadline:
                        raise CommandError(
                            "고정 구간 읽기 시간이 끝났습니다. "
                            "partial 파일은 성공 입력으로 사용하지 않습니다."
                        )
                    batches = consumer.poll(
                        timeout_ms=500, max_records=500
                    )
                    for partition, records in batches.items():
                        if partition not in active:
                            continue
                        for record in records:
                            if record.offset >= ends[partition]:
                                continue
                            if count >= max_records:
                                raise CommandError(
                                    "수업용 레코드 상한을 초과했습니다."
                                )
                            envelope = dict(record.value)
                            envelope.update({
                                "kafka_topic": record.topic,
                                "kafka_partition": record.partition,
                                "kafka_offset": record.offset,
                                "kafka_key": record.key,
                            })
                            destination.write(
                                json.dumps(envelope, ensure_ascii=False)
                                + "\n"
                            )
                            count += 1

                    completed = {
                        partition for partition in active
                        if consumer.position(partition) >= ends[partition]
                    }
                    if completed:
                        consumer.pause(*completed)
                        active -= completed

            temporary.replace(output)
            manifest = {
                "source": "kafka-retained-snapshot",
                "topic": topic,
                "record_count": count,
                "output": str(output),
                "group_committed": False,
                "bounds": [
                    {
                        "partition": partition.partition,
                        "start_inclusive": starts[partition],
                        "end_exclusive": ends[partition],
                    }
                    for partition in partitions
                ],
            }
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        finally:
            consumer.close(autocommit=False)

        self.stdout.write(json.dumps(manifest, ensure_ascii=False, indent=2))