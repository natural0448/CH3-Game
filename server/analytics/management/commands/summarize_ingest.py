import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Summarize the collected Parquet without changing the game summary"

    def add_arguments(self, parser):
        parser.add_argument("--data-dir", default=str(settings.DATA_DIR))
        parser.add_argument("--cores", type=int, choices=[1, 2], default=2)
        parser.add_argument("--event-id")

    def handle(self, *args, **options):
        if not settings.SPARK_MASTER.startswith("spark://"):
            raise CommandError("Use the existing Spark cluster")

        script = settings.PROJECT_DIR / "spark_jobs" / "summarize_ingest.py"
        if not script.is_file():
            raise CommandError(f"Write the Spark summary job first: {script}")

        command = [
            settings.SPARK_SUBMIT,
            "--master", settings.SPARK_MASTER,
            "--deploy-mode", "client",
            "--executor-cores", "1",
            "--total-executor-cores", str(options["cores"]),
            "--conf", f"spark.pyspark.python={sys.executable}",
            "--conf", f"spark.pyspark.driver.python={sys.executable}",
            str(script),
            "--data-dir", str(Path(options["data_dir"]).resolve()),
        ]
        if options["event_id"]:
            try:
                selected_id = str(UUID(options["event_id"]))
            except ValueError as exc:
                raise CommandError("event-id must be a UUID") from exc
            command.extend(["--event-id", selected_id])

        env = os.environ.copy()
        env["PYSPARK_PYTHON"] = sys.executable
        env["PYSPARK_DRIVER_PYTHON"] = sys.executable
        try:
            subprocess.run(command, cwd=settings.BASE_DIR, env=env, check=True)
        except subprocess.CalledProcessError as exc:
            raise CommandError(f"Spark exited with code {exc.returncode}") from exc

