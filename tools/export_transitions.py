import argparse
import json
from collections import defaultdict
from pathlib import Path
from uuid import UUID

TRANSITION_FIELDS = (
    "episode_id", "step", "observation", "action", "reward",
    "next_observation", "done", "terminated", "truncated",
    "policy_version",
)
ENVELOPE_FIELDS = (
    "event_id", "player_id", "room_id", "event_time",
)


def validate_transition(transition):
    missing = set(TRANSITION_FIELDS) - transition.keys()
    if missing:
        raise ValueError(f"transition 필드 누락: {sorted(missing)}")
    UUID(str(transition["episode_id"]))
    step = transition["step"]
    if type(step) is not int or not 1 <= step <= 5:
        raise ValueError("step은 정수 1..5입니다.")
    for name in ("observation", "next_observation"):
        observation = transition[name]
        for field in ("x", "y", "coins"):
            if type(observation.get(field)) is not int:
                raise ValueError(f"{name}.{field}는 정수입니다.")
    action = transition["action"]
    if action.get("type") not in {"move", "gather", "train"}:
        raise ValueError("지원하는 수동 행동이 아닙니다.")
    if action["type"] == "move":
        if action.get("direction") not in {"up", "down", "left", "right"}:
            raise ValueError("move 방향이 없습니다.")
    before = transition["observation"]["coins"]
    after = transition["next_observation"]["coins"]
    if type(transition["reward"]) is not int:
        raise ValueError("reward는 서버 정수 차이입니다.")
    if transition["reward"] != after - before:
        raise ValueError("reward와 coins 차이가 다릅니다.")
    if transition["policy_version"] != "manual-v1":
        raise ValueError("이번 인계는 manual-v1만 처리합니다.")
    for field in ("done", "terminated", "truncated"):
        if type(transition[field]) is not bool:
            raise ValueError(f"{field}는 boolean입니다.")
    if transition["terminated"]:
        raise ValueError("이번 규칙에는 실제 종료가 없습니다.")
    expected_end = step == 5
    if transition["done"] != expected_end:
        raise ValueError("done은 5행 묶음 끝을 뜻합니다.")
    if transition["truncated"] != expected_end:
        raise ValueError("truncated는 5행 길이 제한을 뜻합니다.")

def read_transitions(source):
    selected = {}
    source_count = 0
    skipped = 0
    duplicates = 0
    with source.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            source_count += 1
            event = json.loads(line)
            transition = event.get("payload", {}).get("transition")
            if transition is None:
                skipped += 1
                continue
            try:
                UUID(str(event["event_id"]))
                validate_transition(transition)
                row = {
                    name: event[name] for name in ENVELOPE_FIELDS
                }
                row.update({
                    name: transition[name] for name in TRANSITION_FIELDS
                })
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"입력 {line_number}행: {exc}"
                ) from exc
            event_id = row["event_id"]
            if event_id in selected:
                if selected[event_id] != row:
                    raise ValueError(
                        f"같은 event_id의 내용이 다릅니다: {event_id}"
                    )
                duplicates += 1
                continue
            selected[event_id] = row

    rows = sorted(
        selected.values(),
        key=lambda row: (
            row["player_id"], row["episode_id"], row["step"]
        ),
    )
    return rows, {
        "source_count": source_count,
        "skipped_before_extension": skipped,
        "duplicate_deliveries": duplicates,
    }

def inspect_episodes(rows):
    episodes = defaultdict(list)
    for row in rows:
        episodes[(row["player_id"], row["episode_id"])].append(row)
    complete = 0
    partial = 0
    for key, items in episodes.items():
        items.sort(key=lambda row: row["step"])
        steps = [row["step"] for row in items]
        if len(steps) != len(set(steps)):
            raise ValueError(f"한 묶음에 같은 step이 반복됩니다: {key}")
        for previous, current in zip(items, items[1:]):
            if current["step"] == previous["step"] + 1:
                if previous["next_observation"] != current["observation"]:
                    raise ValueError(f"전후 관측이 연결되지 않습니다: {key}")
        if steps == [1, 2, 3, 4, 5] and items[-1]["done"]:
            complete += 1
        else:
            partial += 1
    return {
        "episode_count": len(episodes),
        "complete_five_step_episodes": complete,
        "partial_episodes": partial,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = Path(args.input).resolve()
    output = Path(args.output).resolve()
    manifest_path = output.with_suffix(".manifest.json")
    if source == output:
        raise ValueError("원본과 출력은 분리합니다.")
    if output.exists() or manifest_path.exists():
        raise ValueError("기존 인계 결과를 보존하고 새 출력 이름을 사용합니다.")

    rows, counts = read_transitions(source)
    episode_counts = inspect_episodes(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as destination:
        for row in rows:
            destination.write(
                json.dumps(row, ensure_ascii=False) + "\n"
            )
    manifest = {
        "schema_version": 1,
        "source": str(source),
        "source_type": "mysql-gameevent-export",
        "output": str(output),
        "exported_count": len(rows),
        "policy_version": "manual-v1",
        "episode_rule": "five-successful-actions; no-world-reset",
        "termination_rule": "terminated=false; truncated=(step==5)",
        "training_performed": False,
        **counts,
        **episode_counts,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()