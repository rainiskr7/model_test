"""무엇: C3 회귀 대조 · 입력: 모델별 이전/새 run 루트 · 출력: 차이 파일명 · 계약 판 4."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jeveval.contract.stages import stage_names
from jeveval.io import records, run_files
from jeveval.io.paths import identifier


def normalize(value, old_id, new_id, *, derived=False, path=()):
    if isinstance(value, dict):
        return {k: normalize(v, old_id, new_id, derived=derived, path=path + (k,)) for k, v in value.items()
                if k != "threshold_sha256" and not (derived and path == ("dev_input",) and k == "sha256")}
    if isinstance(value, list):
        return [normalize(v, old_id, new_id, derived=derived, path=path) for v in value]
    return value.replace(old_id, new_id) if isinstance(value, str) else value


def compare_variant(old, new):
    a, b = (run_files.read_json(p / "fingerprint.json") for p in (old, new))
    for key in ("model", "set", "variant"):
        if a[key] != b[key]:
            return ["fingerprint.json"]
        identifier(a[key])
    old_id, new_id = identifier(a["run_id"]), identifier(b["run_id"])
    stages = stage_names(a["set"])
    derived = (old / "dev/derived.json").is_file()
    if derived != (new / "dev/derived.json").is_file():
        return ["dev/derived.json"]
    differences = []
    for stage in stages:
        name = stage + "/final.jsonl"
        if not all((p / name).is_file() for p in (old, new)):
            differences.append(name)
            continue
        left, right = (run_files.read_bytes(p / name) for p in (old, new))
        if derived:
            left = left.replace(old_id.encode(), new_id.encode())
        if left != right:
            differences.append(name)
        for p in (old, new):
            if records.read_finals(p / name)[1]:
                differences.append(name)
    for name in ("threshold.json", "scores.json", "risk.json", "summary.json"):
        if derived and name == "summary.json" and not any((p / name).exists() for p in (old, new)):
            continue
        if not all((p / name).is_file() for p in (old, new)):
            differences.append(name)
            continue
        left, right = (run_files.read_json(p / name) for p in (old, new))
        if normalize(left, old_id, new_id, derived=derived) != normalize(right, new_id, new_id, derived=derived):
            differences.append(name)
    return sorted(set(differences))


def audit(old_root, new_root):
    old, new = Path(old_root), Path(new_root)
    variants = [{p.parent.relative_to(root) for p in root.glob("A/*/*/fingerprint.json")} for root in (old, new)]
    if not variants[0] or not variants[1]:
        raise ValueError("run missing")
    differences = []
    for relative in sorted(variants[0] | variants[1]):
        if relative not in variants[0] & variants[1]:
            differences.append((relative / "fingerprint.json").as_posix())
        else:
            differences.extend((relative / name).as_posix() for name in compare_variant(old / relative, new / relative))
    return dict(ok=not differences, differences=differences, n_variants=len(variants[0] | variants[1]))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("arguments")
        result = audit(*sys.argv[1:])
    except Exception:
        result = dict(ok=False, error="audit input or comparison failed")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if result["ok"] else 1)
