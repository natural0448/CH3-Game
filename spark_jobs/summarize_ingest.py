import argparse
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from pyspark.sql import SparkSession, functions as F
from game_ingest import write_json_atomic


def small_groups(frame, column):
    grouped = frame.groupBy(column).count().orderBy(column).limit(1001).collect()
    if len(grouped) > 1000:
        raise ValueError(f"Too many groups for a classroom JSON: {column}")
    return [{column: row[column], "count": int(row["count"])} for row in grouped]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--event-id")
    args = parser.parse_args()
    selected_id = str(UUID(args.event_id)) if args.event_id else None
    data_dir = Path(args.data_dir).resolve()
    source_path = data_dir / "stream" / "game-actions-parquet"
    if not source_path.is_dir():
        raise ValueError("Run game ingestion and observe its output first")
    spark = (
        SparkSession.builder.appName("village-ingest-summary")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    rows = None
    unique = None

    try:
        rows = spark.read.parquet(str(source_path)).cache()
        valid = rows.where(F.col("parse_status") == "valid")
        unique = valid.dropDuplicates(["event_id"]).cache()
        statuses = {
            row["parse_status"]: int(row["count"])
            for row in rows.groupBy("parse_status").count().collect()
        }
        record_count = sum(statuses.values())
        valid_count = statuses.get("valid", 0)
        event_count = unique.count()
        time_range = unique.agg(
            F.min("event_ts").cast("string").alias("first"),
            F.max("event_ts").cast("string").alias("last"),
        ).first()
        sample_ids = [
            row["event_id"]
            for row in unique.select("event_id").orderBy("event_id").limit(10).collect()
        ]
        result = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "kafka-parquet",
            "basis": "all-collected-records",
            "record_count": record_count,
            "valid_record_count": valid_count,
            "invalid_record_count": statuses.get("invalid", 0),
            "unsupported_record_count": statuses.get("unsupported", 0),
            "event_count": int(event_count),
            "duplicate_record_count": int(valid_count - event_count),
            "by_action": small_groups(unique, "event_type"),
            "by_room": small_groups(unique, "room_id"),
            "event_time_min_utc": time_range["first"],
            "event_time_max_utc": time_range["last"],
            "sample_event_ids": sample_ids,
        }
        write_json_atomic(data_dir / "marts" / "stream-summary.json", result)
        print(f"records={record_count} events={event_count}", flush=True)
        if selected_id is not None:
            selected = rows.where(F.col("event_id") == selected_id)
            matched_count = selected.count()
            details = selected.select(
                "event_id", "event_type", "player_id", "room_id",
                "kafka_topic", "kafka_partition", "kafka_offset",
                "kafka_key", "parse_status", "raw_value",
            ).orderBy("kafka_topic", "kafka_partition", "kafka_offset").limit(20).collect()
            evidence = {
                "schema_version": 1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "requested_event_id": selected_id,
                "matched_records": int(matched_count),
                "returned_records": len(details),
                "matches": [row.asDict(recursive=True) for row in details],
                "scope": "selected-event-in-collected-parquet",
            }
            target = data_dir / "evidence" / "day15" / f"event-{selected_id}.json"
            write_json_atomic(target, evidence)
            print(f"selected_event_matches={matched_count}", flush=True)
    finally:
        if unique is not None:
            unique.unpersist()
        if rows is not None:
            rows.unpersist()
        spark.stop()


if __name__ == "__main__":
    main()
