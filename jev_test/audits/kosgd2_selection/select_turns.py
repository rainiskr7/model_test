"""무엇: kosgd2 풀 밖 대표 선정 · 입력: 원본 대화/옛 선정 · 출력: ID·해시·건수 · 개정 15."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import random

SEED = 20261019


def select(dialogues, excluded):
    """대화 ID 정렬 뒤 옛 대화를 제외하고 USER 위치 하나를 동일 RNG로 고른다."""
    ids = [d["dialogue_id"] for d in dialogues]
    if any(not isinstance(i, str) or not i or ":" in i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("invalid dialogue identities")
    if not excluded <= set(ids):
        raise ValueError("excluded dialogue missing from source")
    rng, selected, missing = random.Random(SEED), [], 0
    for dialogue in sorted(dialogues, key=lambda d: d["dialogue_id"]):
        did = dialogue["dialogue_id"]
        if did in excluded:
            continue
        indices = [i for i, t in enumerate(dialogue["turns"]) if t["speaker"] == "USER"]
        if not indices:
            missing += 1
            continue
        selected.append(dict(dialogue_id=did, turn_index=rng.choice(indices)))
    if {row["dialogue_id"] for row in selected} & excluded:
        raise ValueError("selection intersects old pool")
    return selected, missing


def run(source, excluded_path, out):
    paths = sorted(Path(source).glob("dialogues_*.json"))
    if not paths:
        raise ValueError("source unavailable")
    dialogues = [d for p in paths for d in json.loads(p.read_text(encoding="utf-8"))]
    payload = Path(excluded_path).read_bytes()
    old = json.loads(payload)["selected_turns"]
    excluded = {row["dialogue_id"] for row in old}
    if len(excluded) != len(old):
        raise ValueError("duplicate exclusion identity")
    selected, missing = select(dialogues, excluded)
    result = dict(schema="kosgd2_selection/1", seed=SEED, excluded_source="kosgd",
                  excluded_sha256=sha256(payload).hexdigest(), n_dialogues_total=len(dialogues),
                  n_excluded=len(excluded), n_without_user=missing, selected_turns=selected)
    target = Path(out)
    if target.exists():
        raise ValueError("selection output already exists")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return dict(G=len(selected), n_without_user=missing, intersection=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Select kosgd2 turns without model calls")
    parser.add_argument("--source", required=True)
    parser.add_argument("--excluded", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args.source, args.excluded, args.out)
    except (ValueError, TypeError, KeyError, OSError):
        parser.exit(1, "selection: invalid input\n")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
