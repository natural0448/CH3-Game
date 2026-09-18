import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run independent game-actions ingestion on the existing cluster"

    def add_arguments(self, parser):
        parser.add_argument("--data-dir", default=str(settings.DATA_DIR))
        parser.add_argument("--mode", choices=["continuous", "available-now"], default="continuous")
        parser.add_argument("--cores", type=int, choices=[1, 2], default=2)
        parser.add_argument("--max-offsets", type=int, default=1000)
        parser.add_argument("--trigger-seconds", type=int, default=5)

    def handle(self, *args, **options):
        if not settings.SPARK_MASTER.startswith("spark://"):
            raise CommandError("Use the existing standalone master")
        if options["max_offsets"] < 1 or options["trigger_seconds"] < 1:
            raise CommandError("Rate and interval values must be positive")
        script = settings.PROJECT_DIR / "spark_jobs" / "game_ingest.py"
        if not script.is_file():
            raise CommandError(f"Write the Spark job first: {script}")
        command = [
            settings.SPARK_SUBMIT,
            "--master", settings.SPARK_MASTER,
            "--deploy-mode", "client",
            "--executor-cores", "1",
            "--total-executor-cores", str(options["cores"]),
            "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.1.3",
            "--conf", f"spark.pyspark.python={sys.executable}",
            "--conf", f"spark.pyspark.driver.python={sys.executable}",
            str(script),
            "--data-dir", str(Path(options["data_dir"]).resolve()),
            "--bootstrap-servers", ",".join(settings.KAFKA_BOOTSTRAP_SERVERS),
            "--topic", "game.actions.v1",
            "--mode", options["mode"],
            "--max-offsets", str(options["max_offsets"]),
            "--trigger-seconds", str(options["trigger_seconds"]),
        ]
        env = os.environ.copy()
        env["PYSPARK_PYTHON"] = sys.executable
        env["PYSPARK_DRIVER_PYTHON"] = sys.executable
        self.stdout.write(f"master={settings.SPARK_MASTER}")
        self.stdout.write(f"script={script}")
        try:
            subprocess.run(command, cwd=settings.BASE_DIR, env=env, check=True)
        except KeyboardInterrupt:
            self.stdout.write("Stop requested; preserve output and checkpoint.")
        except subprocess.CalledProcessError as exc:
            raise CommandError(f"Spark exited with code {exc.returncode}") from exc