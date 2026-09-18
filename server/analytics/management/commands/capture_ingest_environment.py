import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Record the configured ingestion environment without running Spark"

    def handle(self, *args, **options):
        master = settings.SPARK_MASTER
        if not isinstance(master, str) or not master.startswith("spark://"):
            raise CommandError("SPARK_MASTER must point to the existing standalone cluster")
        submit = Path(settings.SPARK_SUBMIT).expanduser().resolve()
        if not submit.is_file():
            raise CommandError("SPARK_SUBMIT does not point to a file")
        target = settings.DATA_DIR / "evidence" / "day15" / "environment.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "schema_version": 1,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "evidence_kind": "configuration-observation",
            "spark_executed": False,
            "python": sys.version.split()[0],
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "spark_submit": str(submit),
            "spark_master": master,
            "kafka_bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "kafka_topic": "game.actions.v1",
            "spark_package": "org.apache.spark:spark-sql-kafka-0-10_2.13:4.1.3",
            "project_dir": str(settings.PROJECT_DIR),
            "data_dir": str(settings.DATA_DIR),
        }
        target.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(str(target))