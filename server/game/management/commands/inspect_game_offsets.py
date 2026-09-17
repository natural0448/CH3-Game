import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from kafka import KafkaConsumer, TopicPartition


class Command(BaseCommand):
    help = "Read offsets without consuming or committing game events."

    def add_arguments(self, parser):
        parser.add_argument("--topic", default="game.events.v1")
        parser.add_argument("--group", default="day13-analysis-a")

    def handle(self, *args, **options):
        consumer = KafkaConsumer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=options["group"],
            enable_auto_commit=False,
            request_timeout_ms=15000,
        )
        rows = []
        try:
            topic = options["topic"]
            numbers = consumer.partitions_for_topic(topic)
            if numbers is None:
                raise CommandError("Topic metadata is unavailable.")
            partitions = [
                TopicPartition(topic, number)
                for number in sorted(numbers)
            ]
            beginnings = consumer.beginning_offsets(partitions)
            ends = consumer.end_offsets(partitions)

            for tp in partitions:
                saved = consumer.committed(tp)
                rows.append({
                    "topic": tp.topic,
                    "partition": tp.partition,
                    "beginning_offset": beginnings[tp],
                    "end_offset": ends[tp],
                    "committed_offset": saved,
                    "has_committed_offset": saved is not None,
                })

        finally:
            consumer.close(autocommit=False)
        self.stdout.write(json.dumps({
            "group_id": options["group"],
            "partitions": rows,
        }, ensure_ascii=False, indent=2))