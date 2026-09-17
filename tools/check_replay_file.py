import json
from pathlib import Path

source = Path("data-replay/raw/game-events.jsonl")
manifest = json.loads(
    source.with_suffix(".manifest.json").read_text(encoding="utf-8")
)
bounds = {
    row["partition"]: (row["start_inclusive"], row["end_exclusive"])
    for row in manifest["bounds"]
}
rows = 0
event_ids = set()
with source.open(encoding="utf-8") as stream:
    for line in stream:
        if not line.strip():
            continue
        event = json.loads(line)
        start, end = bounds[event["kafka_partition"]]
        assert start <= event["kafka_offset"] < end
        assert event["kafka_topic"] == manifest["topic"]
        rows += 1
        event_ids.add(event["event_id"])
assert rows == manifest["record_count"]
print({
    "raw_records": rows,
    "unique_events": len(event_ids),
    "delivery_duplicates": rows - len(event_ids),
    "bounds_checked": True,
})