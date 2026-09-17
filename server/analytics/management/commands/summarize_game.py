import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "행동 로그를 기존 Native Spark 클러스터에서 집계합니다."

    def add_arguments(self, parser):
        parser.add_argument("--source", choices=["raw"], default="raw")
        parser.add_argument("--data-dir", default=str(settings.DATA_DIR))
        parser.add_argument("--cores", type=int, choices=[1, 2], default=2)


    def handle(self, *args, **options):
        command = [
            settings.SPARK_SUBMIT,
            "--master", settings.SPARK_MASTER,
            "--deploy-mode", "client",
            "--executor-cores", "1",
            "--total-executor-cores", str(options["cores"]),
            "--conf", f"spark.pyspark.python={sys.executable}",
            "--conf", f"spark.pyspark.driver.python={sys.executable}",
            str(settings.PROJECT_DIR / "spark_jobs" / "game_batch.py"),
            "--data-dir", str(Path(options["data_dir"]).resolve()),
            "--source", options["source"],
        ]
        env = os.environ.copy()
        env["PYSPARK_PYTHON"] = sys.executable
        env["PYSPARK_DRIVER_PYTHON"] = sys.executable
        subprocess.run(command, cwd=settings.BASE_DIR, env=env, check=True)
