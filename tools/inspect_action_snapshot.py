import argparse
import json
from collections import Counter
from pathlib import Path


def inspect(source):
    rows = 0
    unique = {}
    with_transition = 0
    with_label = 0
    manifest = json.loads(
        source.with_suffix(".manifest.json").read_text(encoding="utf-8")
    )
    bounds = {
        row["partition"]: (row["start_inclusive"], row["end_exclusive"])
        for row in manifest["bounds"]
    }
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        start, end = bounds[event["kafka_partition"]]
        if not start <= event["kafka_offset"] < end:
            raise ValueError("snapshot의 고정 범위를 벗어난 위치입니다.")
        if event["kafka_topic"] != "game.actions.v1":
            raise ValueError("행동 Topic snapshot이 아닙니다.")
        rows += 1
        with_label += "action_label" in event["payload"]
        with_transition += "transition" in event["payload"]
        fact = {
            key: event[key] for key in (
                "schema_version", "event_id", "event_type", "player_id",
                "room_id", "event_time", "payload",
            )
        }
        event_id = fact["event_id"]
        if event_id in unique:
            previous = unique[event_id]
            left = dict(previous["payload"])
            right = dict(fact["payload"])
            left.pop("action_label", None)
            right.pop("action_label", None)
            same_outer = all(
                previous[key] == fact[key]
                for key in fact if key != "payload"
            )
            if not same_outer or left != right:
                raise ValueError("같은 사건의 원본 내용이 서로 다릅니다.")
        else:
            unique[event_id] = fact

    if rows != manifest["record_count"]:
        raise ValueError("manifest record_count와 파일 줄 수가 다릅니다.")
    by_action = Counter(
        event["event_type"] for event in unique.values()
    )
    return {
        "source_topic": manifest["topic"],
        "raw_records": rows,
        "unique_events": len(unique),
        "delivery_duplicates": rows - len(unique),
        "rows_with_action_label": with_label,
        "rows_with_transition": with_transition,
        "unique_by_action": dict(sorted(by_action.items())),
        "bounds_checked": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    report = inspect(Path(args.input).resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()