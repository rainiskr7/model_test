"""무엇: 봉인/진입 시험 도우미 · 입력: 합성 fixture · 출력: 실행 폴더·분할 · 계약 §8-6 A."""

import json

from jeveval.types import SplitPlan


def put(root, name, raw):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
    return path


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None
            for p in root.rglob("*")}


def plan_for(logical_id="synthetic:g:ok"):
    name, group, item = logical_id.split(":")
    return SplitPlan(name, 1, {}, {}, {group: [item], "t": ["i"]},
                     {group: logical_id, "t": f"{name}:t:i"}, [group], ["t"], [], [], {})


def install_case(root, case, *, sealed=False):
    put(root, "dev/final.jsonl", case["dev_final_raw"])
    if case["threshold_raw"] is not None:
        put(root, "threshold.json", case["threshold_raw"])
    if sealed:
        put(root, "test/seal.json", json.dumps(case["seal"]))
