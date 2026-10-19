"""무엇: C4 부분 재판정 진단 · 입력: 모델별 새/출처 run 루트 · 출력: ID 집합 대조·집계 · 계약 판 4."""

from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jeveval.io import records, run_files
from jeveval.io.paths import identifier


def summary(current, source):
    finals, pending = records.read_finals(current)
    originals, old_pending = records.read_finals(source)
    if pending or old_pending or not current.is_file() or not source.is_file():
        raise ValueError("incomplete file")
    actual, expected = {f.logical_id for f in finals}, {f.logical_id for f in originals}
    statuses, warnings = Counter(), Counter()
    # 공개 출력에는 알려진 진단 코드만 쓴다. 임의 기록 문자열은 원문일 수 있다.
    known = {"extra_keys", "usage_input_tokens_invalid", "confidence_differs", "choice_not_argmax",
             "length_mismatch", "b1_extra_token", "b1_duplicate_label"}
    for final in finals:
        statuses[final.status if final.status in {"ok", "error", "rejected", "truncated"} else "unknown"] += 1
        warnings.update(w if w in known else "unknown" for w in set(final.warnings))
    bad = sum(f.reason == "choice_pick" or any(c.reason == "choice_pick" for c in f.calls) for f in finals)
    return dict(ids_equal=actual == expected, n_final=len(finals), n_source_final=len(originals),
                n_missing=len(expected - actual), n_unexpected=len(actual - expected),
                n_choice_pick=bad, by_status=dict(statuses), warnings=dict(warnings))


def audit(run_root, source_root):
    current, source = Path(run_root), Path(source_root)
    source_variants = sorted(source.glob("A/*/*/fingerprint.json"))
    if not source_variants:
        raise ValueError("source run missing")
    rows = []
    for path in source_variants:
        fp = run_files.read_json(path)
        relative = path.parent.relative_to(source)
        for key in ("model", "set", "variant"):
            identifier(fp[key])
        for stage in ("dev", "test", "extra"):
            old = path.parent / stage / "final.jsonl"
            if not old.exists():
                continue
            if (path.parent / stage / "derived.json").exists():
                continue
            row = summary(current / relative / stage / "final.jsonl", old)
            rows.append(dict(set=fp["set"], variant=fp["variant"], stage=stage, **row))
    return dict(ok=bool(rows) and all(r["ids_equal"] and not r["n_choice_pick"] for r in rows), rows=rows)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("arguments")
        result = audit(*sys.argv[1:])
    except Exception:
        result = dict(ok=False, error="audit input or summary failed")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if result["ok"] else 1)
