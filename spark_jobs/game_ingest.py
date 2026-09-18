import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import (
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)

ACTION_TYPES = ("player.moved", "player.gathered", "player.trained")

EVENT_SCHEMA = StructType([
    StructField("schema_version", IntegerType()),
    StructField("event_id", StringType()),
    StructField("event_type", StringType()),
    StructField("player_id", LongType()),
    StructField("room_id", StringType()),
    StructField("event_time", StringType()),
    StructField("payload", StructType([
        StructField("action_label", StringType()),
        StructField("version", LongType()),
    ])),
])

def read_kafka(spark, bootstrap_servers, topic, max_offsets):
    return (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", bootstrap_servers)
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "true")
        .option("maxOffsetsPerTrigger", str(max_offsets))
        .option("groupIdPrefix", "village-spark-ingest")
        .load()
    )


def project_events(source):
    raw = source.select(
        F.col("key").cast("string").alias("kafka_key"),
        F.col("value").cast("string").alias("raw_value"),
        F.col("topic").alias("kafka_topic"),
        F.col("partition").alias("kafka_partition"),
        F.col("offset").alias("kafka_offset"),
        F.col("timestamp").alias("kafka_timestamp"),
    )
    parsed = raw.withColumn("event", F.from_json("raw_value", EVENT_SCHEMA))
    projected = parsed.select(
        "kafka_key", "raw_value", "kafka_topic",
        "kafka_partition", "kafka_offset", "kafka_timestamp",
        F.col("event.schema_version").alias("schema_version"),
        F.col("event.event_id").alias("event_id"),
        F.col("event.event_type").alias("event_type"),
        F.col("event.player_id").alias("player_id"),
        F.col("event.room_id").alias("room_id"),
        F.col("event.event_time").alias("event_time"),
        F.col("event.payload.action_label").alias("action_label"),
        F.col("event.payload.version").alias("player_version"),
        F.get_json_object("raw_value", "$.payload").alias("payload_json"),
    )

    timed = projected.withColumn(
        "event_ts", F.try_to_timestamp(F.col("event_time"))
    )
    required_ok = (
        F.col("event_id").isNotNull()
        & (F.length("event_id") > 0)
        & F.col("player_id").isNotNull()
        & F.col("room_id").isNotNull()
        & F.col("event_ts").isNotNull()
        & F.col("action_label").isNotNull()
    )
    return (
        timed.withColumn(
            "parse_status",
            F.when(~F.coalesce(required_ok, F.lit(False)), F.lit("invalid"))
            .when(F.col("schema_version") != 1, F.lit("unsupported"))
            .when(~F.col("event_type").isin(*ACTION_TYPES), F.lit("unsupported"))
            .when(F.col("schema_version").isNull(), F.lit("invalid"))
            .when(F.col("event_type").isNull(), F.lit("invalid"))
            .otherwise(F.lit("valid")),
        )
        .withColumn("ingested_at", F.current_timestamp())
    )

def write_json_atomic(target, document):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=target.name + ".", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--bootstrap-servers", required=True)
    parser.add_argument("--topic", default="game.actions.v1")
    parser.add_argument("--mode", choices=["continuous", "available-now"], default="continuous")
    parser.add_argument("--max-offsets", type=int, default=1000)
    parser.add_argument("--trigger-seconds", type=int, default=5)
    args = parser.parse_args()
    if args.max_offsets < 1 or args.trigger_seconds < 1:
        parser.error("max-offsets and trigger-seconds must be positive")
    return args

def main():
    args = parse_args()
    data_dir = Path(args.data_dir).resolve()
    output_dir = data_dir / "stream" / "game-actions-parquet"
    checkpoint_dir = data_dir / "checkpoints" / "game-ingest-v1"
    progress_path = data_dir / "marts" / "ingest-progress.json"
    spark = (
        SparkSession.builder.appName("village-game-ingest")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    query = None
    try:
        source = read_kafka(spark, args.bootstrap_servers, args.topic, args.max_offsets)
        rows = project_events(source)
        rows.printSchema()

        writer = (
            rows.writeStream.format("parquet").outputMode("append")
            .queryName("village-game-ingest-v1")
            .option("path", str(output_dir))
            .option("checkpointLocation", str(checkpoint_dir))
        )
        if args.mode == "available-now":
            writer = writer.trigger(availableNow=True)
        else:
            writer = writer.trigger(processingTime=f"{args.trigger_seconds} seconds")
        query = writer.start()

        last_written_batch = None
        while query.isActive:
            progress = query.lastProgress
            if progress is not None and progress["batchId"] != last_written_batch:
                document = {
                    "schema_version": 1,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "query_name": "village-game-ingest-v1",
                    "topic": args.topic,
                    "batch_id": progress["batchId"],
                    "batch_input_rows": progress["numInputRows"],
                    "input_rows_per_second": progress["inputRowsPerSecond"],
                    "processed_rows_per_second": progress["processedRowsPerSecond"],
                    "progress_timestamp": progress["timestamp"],
                    "sources": progress.get("sources", []),
                    "meaning": "last-observed-completed-micro-batch",
                }
                write_json_atomic(progress_path, document)
                print(json.dumps({
                    "batch_id": document["batch_id"],
                    "batch_input_rows": document["batch_input_rows"],
                }), flush=True)
                last_written_batch = progress["batchId"]
            query.awaitTermination(1)
        query.awaitTermination()
    except KeyboardInterrupt:
        print("Stopping ingestion; output and checkpoint are preserved.", flush=True)
    finally:
        if query is not None and query.isActive:
            query.stop()
        spark.stop()


if __name__ == "__main__":
    main()