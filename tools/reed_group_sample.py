import json
from pathlib import Path

def read_ids(path):
    with Path(path).open(encoding="utf-8") as source:
        return {
            json.loads(line)["event_id"]
            for line in source if line.strip()
        }

left = read_ids("data/group-samples/a.jsonl")
right = read_ids("data/group-samples/b.jsonl")
print({
    "a_unique": len(left),
    "b_unique": len(right),
    "shared_event_ids": len(left & right),
})