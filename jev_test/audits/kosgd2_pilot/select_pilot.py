"""라벨을 사용하지 않는 1회 파일럿 선정. 원문 없이 ID·해시만 출력한다."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jeveval.data.exclusions import dialogue_ids


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def select(dialogues, old, t0, new):
    ids = [r["dialogue_id"] for r in old]
    if len(ids) != 3000 or len(set(ids)) != 3000:
        raise ValueError("old pool requires 3000 unique dialogues")
    by_id = {d["dialogue_id"]: d for d in dialogues}
    if len(by_id) != len(dialogues) or not set(ids) <= by_id.keys():
        raise ValueError("source identities incomplete")
    if set(ids) & set(t0):
        raise ValueError("old pool overlaps T0")
    rng = random.Random(20261019)
    chosen = sorted(rng.sample(sorted(ids), 200))
    if set(chosen) & (set(t0) | set(new)):
        raise ValueError("pilot intersects held-out pool")
    result = []
    for did in chosen:
        indices = [i for i, t in enumerate(by_id[did]["turns"]) if t["speaker"] == "USER"]
        if not indices:
            raise ValueError("selected dialogue has no USER")
        result.append(dict(dialogue_id=did, turn_index=rng.choice(indices)))
    return result


def run(source, old, fixture, new, out):
    paths = sorted(Path(source).glob("dialogues_*.json"))
    if not paths:
        raise ValueError("source unavailable")
    payloads = {str(p): p.read_bytes() for p in [*paths, Path(old), Path(fixture), Path(new)]}
    data = lambda p: json.loads(payloads[str(p)])
    selected = select([d for p in paths for d in data(p)], data(old)["selected_turns"],
                      dialogue_ids(data(fixture)["cases"], "state_ref"),
                      {r["dialogue_id"] for r in data(new)["selected_turns"]})
    value = dict(schema="kosgd2_pilot_selection/1", seed=20261019, python=platform.python_version(),
                 inputs={k: hashlib.sha256(v).hexdigest() for k, v in payloads.items()},
                 selected_turns=selected, selection_sha256=digest(selected))
    with Path(out).open("x", encoding="utf-8") as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=1) + "\n")
    return dict(ok=True, count=200, selection_sha256=value["selection_sha256"])


def main():
    p = argparse.ArgumentParser()
    for name in ("source", "old", "fixture", "new", "out"):
        p.add_argument("--" + name, required=True)
    try:
        print(json.dumps(run(**vars(p.parse_args()))))
    except Exception:
        print('{"ok":false,"error":"pilot selection input or output invalid"}')
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
