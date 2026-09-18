import argparse
import json
from copy import deepcopy
from pathlib import Path
from uuid import UUID

KAFKA_FIELDS = {
    "kafka_topic", "kafka_partition", "kafka_offset", "kafka_key",
}


def matching_rows(path, event_id):
    rows = []
    with path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("event_id") == event_id:
                rows.append(event)
    return rows


def check(source_path, actions_path, event_id):
    originals = matching_rows(source_path, event_id)
    derived = matching_rows(actions_path, event_id)
    if not originals:
        raise ValueError("지정한 event_id가 원본 파일에 없습니다.")
    if not derived:
        raise ValueError("지정한 event_id가 이 snapshot 범위에 없습니다.")
    original = originals[0]
    for row in originals[1:]:
        if row != original:
            raise ValueError("원본에서 같은 event_id의 내용이 다릅니다.")

    output_positions = []
    labels = set()
    for row in derived:
        payload = deepcopy(row["payload"])
        label = payload.pop("action_label", None)
        if not isinstance(label, str) or not label:
            raise ValueError("파생 기록의 표시 이름이 없습니다.")
        candidate = {
            key: value for key, value in row.items()
            if key not in KAFKA_FIELDS
        }
        candidate["payload"] = payload
        expected = deepcopy(original)
        expected["payload"].pop("action_label", None)
        if candidate != expected:
            raise ValueError("표시 필드 이외의 원본 값이 달라졌습니다.")
        if row["kafka_topic"] != "game.actions.v1":
            raise ValueError("출력 Topic이 다릅니다.")
        if row["kafka_key"] != str(original["player_id"]):
            raise ValueError("출력 key가 원래 player_id와 다릅니다.")
        labels.add(label)
        output_positions.append({
            "partition": row["kafka_partition"],
            "offset": row["kafka_offset"],
        })
    return {
        "event_id": event_id,
        "event_type": original["event_type"],
        "player_id": original["player_id"],
        "source_rows": len(originals),
        "derived_rows": len(derived),
        "action_labels": sorted(labels),
        "source_fields_preserved": True,
        "transition_preserved": "transition" in original["payload"],
        "output_positions": output_positions,
        "comparison_scope": "one-server-fact",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--actions", required=True)
    parser.add_argument("--event-id", required=True)
    args = parser.parse_args()
    event_id = str(UUID(args.event_id))
    report = check(
        Path(args.source).resolve(),
        Path(args.actions).resolve(),
        event_id,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()