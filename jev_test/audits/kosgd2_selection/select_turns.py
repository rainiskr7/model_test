"""무엇: kosgd2 풀 밖 대표 선정 · 입력: 원본 대화/옛 선정 · 출력: ID·해시·건수 · 개정 15."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from jeveval.data.exclusions import dialogue_ids

SEED = 20261019


def select(dialogues, excluded, held_out=frozenset()):
    """대화 ID 정렬 뒤 옛 대화를 제외하고 USER 위치 하나를 동일 RNG로 고른다."""
    ids = [d["dialogue_id"] for d in dialogues]
    if any(not isinstance(i, str) or not i or ":" in i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("invalid dialogue identities")
    if not excluded <= set(ids):
        raise ValueError("excluded dialogue missing from source")
    if not held_out <= set(ids):
        raise ValueError("T0 dialogue missing from source")
    if held_out & excluded:
        raise ValueError("T0 dialogue intersects old pool")
    rng, selected, missing = random.Random(SEED), [], 0
    for dialogue in sorted(dialogues, key=lambda d: d["dialogue_id"]):
        did = dialogue["dialogue_id"]
        if did in excluded:
            continue
        indices = [i for i, t in enumerate(dialogue["turns"]) if t["speaker"] == "USER"]
        if not indices:
            missing += 1
            continue
        turn = rng.choice(indices)  # T0 대화도 RNG를 소비하고 결과에서만 뺀다.
        if did not in held_out:
            selected.append(dict(dialogue_id=did, turn_index=turn))
    if {row["dialogue_id"] for row in selected} & (excluded | held_out):
        raise ValueError("selection intersects old pool")
    return selected, missing


def run(source, excluded_path, out, fixture_path):
    paths = sorted(Path(source).glob("dialogues_*.json"))
    if not paths:
        raise ValueError("source unavailable")
    dialogues = [d for p in paths for d in json.loads(p.read_text(encoding="utf-8"))]
    payload = Path(excluded_path).read_bytes()
    old = json.loads(payload)["selected_turns"]
    excluded = {row["dialogue_id"] for row in old}
    if len(excluded) != len(old):
        raise ValueError("duplicate exclusion identity")
    fixture_bytes = Path(fixture_path).read_bytes()
    fixture = json.loads(fixture_bytes)
    if fixture.get("schema") != "t0_fixture/1":
        raise ValueError("T0 fixture required")
    held_out = dialogue_ids(fixture["cases"], "state_ref")
    if not held_out:
        raise ValueError("KoSGD T0 references required")
    selected, missing = select(dialogues, excluded, held_out)
    result = dict(schema="kosgd2_selection/1", seed=SEED, excluded_source="kosgd",
                  excluded_sha256=sha256(payload).hexdigest(), n_dialogues_total=len(dialogues),
                  t0_fixture_sha256=sha256(fixture_bytes).hexdigest(),
                  exclusion_reason="frozen_boundary_t0_out_of_pool", n_t0_excluded=len(held_out - excluded),
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
    parser.add_argument("--t0-fixture", required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args.source, args.excluded, args.out, args.t0_fixture)
    except (ValueError, TypeError, KeyError, OSError):
        parser.exit(1, "selection: invalid input\n")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
