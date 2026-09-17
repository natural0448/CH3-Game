import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", required=True)
parser.add_argument("--source", choices=["raw"], default="raw")
args = parser.parse_args()
data_dir = Path(args.data_dir).resolve()

spark = (SparkSession.builder.appName("village-game-batch")
    .config("spark.sql.session.timeZone", "Asia/Seoul")
    .config("spark.sql.shuffle.partitions", "2")
    .getOrCreate())

schema = "schema_version int, event_id string, event_type string, player_id long, room_id string, event_time string, payload struct<command_id:string,x:int,y:int,coins:long,version:long>"
records = spark.read.schema(schema).json((data_dir / "raw" / "game-events.jsonl").as_uri())
records.printSchema()

records.select("event_id", "event_type", "room_id", "payload.x", "payload.version")
# 위 줄은 변환 예시다. 실제 미리보기는 다음 줄로 실행한다.
records.select("event_id", "event_type", "room_id", "payload.x", "payload.version").orderBy("event_id").show(5, truncate=False)

actions = (
    records
    .filter(
        (F.col("schema_version") == 1)
        & F.col("event_id").isNotNull()
    )
    .select("event_id", "room_id", "event_type")
    .dropDuplicates(["event_id"])
)

record_count = records.count()
event_count = actions.count()

by_action = [
    row.asDict()
    for row in actions.groupBy("event_type")
    .count()
    .orderBy("event_type")
    .collect()
]

by_room = [
    row.asDict()
    for row in actions.groupBy("room_id")
    .count()
    .orderBy(F.desc("count"), "room_id")
    .limit(20)
    .collect()
]

summary = {
    "schema_version": 1,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "source": args.source,
    "record_count": record_count,
    "event_count": event_count,
    "by_action": by_action,
    "by_room": by_room,
}

output = data_dir / "marts"
output.mkdir(parents=True, exist_ok=True)

temporary = output / "game-summary.json.tmp"
temporary.write_text(
    json.dumps(summary, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
temporary.replace(output / "game-summary.json")

print(json.dumps(summary, ensure_ascii=False))
spark.stop()
