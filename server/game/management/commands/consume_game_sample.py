import json  # 이벤트를 JSON으로 읽고 저장
import os  # 파일 내용을 디스크에 반영하는 fsync 사용
import time  # 새 메시지가 없는 대기 시간 측정
from pathlib import Path  # 출력 파일 경로 처리

from django.conf import settings  # Django에 설정된 Kafka 연결 정보
from django.core.management.base import BaseCommand, CommandError
from kafka import KafkaConsumer, TopicPartition
from kafka.structs import OffsetAndMetadata


class Command(BaseCommand):
    # python manage.py help <명령어>에서 표시되는 설명
    help = "별도 분석 group의 이벤트를 JSONL에 저장하고 다음 위치를 commit"

    def add_arguments(self, parser):
        # 분석용 consumer group: 같은 group은 이전에 commit한 위치부터 이어 읽음
        parser.add_argument("--group", default="day13-analysis-a")
        # 이번 실행에서 처리할 최대 이벤트 수
        parser.add_argument("--limit", type=int, default=6)
        # 새 메시지가 없을 때 종료까지 기다릴 시간
        parser.add_argument("--idle-seconds", type=int, default=10)
        # JSONL 저장 경로: 실행할 때 반드시 지정
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        # 실행 명령에 입력한 옵션을 가져옴
        limit = options["limit"]
        idle_seconds = options["idle_seconds"]
        group = options["group"]

        # 잘못된 옵션이나 수업용이 아닌 group 사용을 차단
        if not 1 <= limit <= 100:
            raise CommandError("--limit은 1..100 범위입니다.")
        if not 1 <= idle_seconds <= 60:
            raise CommandError("--idle-seconds는 1..60 범위입니다.")
        if not group.startswith("day13-analysis-"):
            raise CommandError("수업용 day13-analysis- group만 사용합니다.")

        # 상대 경로를 현재 실행 폴더 기준의 절대 경로로 변환
        output = Path(options["output"]).resolve()
        # 상위 폴더가 없으면 생성하고, 이미 있으면 그대로 사용
        output.parent.mkdir(parents=True, exist_ok=True)

        consumer = KafkaConsumer(
            settings.KAFKA_EVENT_TOPIC,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=group,

            # 파일 저장이 끝난 뒤 직접 commit하기 위해 자동 commit 비활성화
            enable_auto_commit=False,
            # 유효한 commit 위치가 없을 때 보관 중인 가장 오래된 위치부터 읽음
            auto_offset_reset="earliest",
            # Kafka의 bytes key를 문자열로 변환. key가 없으면 None 유지
            key_deserializer=lambda value: (
                value.decode("utf-8") if value is not None else None
            ),

            # Kafka의 bytes value를 JSON 데이터로 변환
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )

        processed = 0

        # 시스템 시각 변경에 영향을 받지 않는 경과 시간으로 종료 시점 계산
        idle_deadline = time.monotonic() + idle_seconds
        try:
            # append 모드: 기존 파일 뒤에 이벤트를 추가
            with output.open("a", encoding="utf-8") as destination:
                while processed < limit:
                    # 최대 0.5초 기다리며 한 번에 최대 1개 레코드를 가져옴
                    batches = consumer.poll(timeout_ms=500, max_records=1)
                    if not batches:
                        # 정해진 시간 동안 메시지가 없으면 정상 종료
                        if time.monotonic() >= idle_deadline:
                            break
                        continue
                    # poll 결과는 TopicPartition별 레코드 목록으로 구성됨
                    for topic_partition, records in batches.items():
                        for record in records:
                            # 원본 이벤트를 복사하고 Kafka에서 읽은 위치를 추가
                            envelope = dict(record.value)
                            envelope["kafka_topic"] = record.topic
                            envelope["kafka_partition"] = record.partition
                            envelope["kafka_offset"] = record.offset
                            envelope["kafka_key"] = record.key

                            # JSONL: 한 줄마다 하나의 JSON 이벤트를 기록
                            destination.write(
                                json.dumps(envelope, ensure_ascii=False) + "\n"
                            )

                            # Python 버퍼를 비우고 운영체제에 디스크 반영을 요청
                            destination.flush()
                            os.fsync(destination.fileno())

                            # 저장한 레코드의 '다음 offset'을 해당 partition에 commit
                            # 예: offset 5를 처리했다면 다음 시작 위치인 6을 기록
                            consumer.commit({
                                TopicPartition(
                                    record.topic, record.partition
                                ): OffsetAndMetadata(record.offset + 1, "", -1)
                            })

                            # 처리 수를 늘리고, 마지막 처리 시점부터 대기 시간을 다시 계산
                            processed += 1
                            idle_deadline = time.monotonic() + idle_seconds

                            # 처리한 이벤트와 commit 위치를 터미널에 출력
                            self.stdout.write(json.dumps({
                                "event_id": envelope["event_id"],
                                "partition": record.partition,
                                "processed_offset": record.offset,
                                "committed_next": record.offset + 1,
                            }, ensure_ascii=False))
        finally:
            # 오류가 발생해도 consumer를 닫음. 종료 시 추가 자동 commit은 하지 않음
            consumer.close(autocommit=False)

        # 정상 종료 시 이번 실행의 처리 결과를 출력
        self.stdout.write(json.dumps({
            "group": group,
            "processed": processed,
            "output": str(output),
        }, ensure_ascii=False))