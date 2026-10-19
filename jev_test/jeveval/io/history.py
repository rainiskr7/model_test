"""무엇: 역사 산출물 읽기 · 입력: root/변형 경로 · 출력: History · 계약 §5-1b; 쓰기 없음."""

from pathlib import Path

from jeveval.io import records, run_files
from jeveval.data.split import check_split_plan
from jeveval.io.hashes import sha256_file
from jeveval.io.paths import inside
from jeveval.io.splits import read_split_plan
from jeveval.io.config import load_taskspec
from jeveval.types.history import History, HistoryStage

FILES = ("fingerprint.json", "threshold.json", "test/seal.json", "risk.json",
         "scores.json", "summary.json", "question_risk.json")


def _json(root, directory, name, artifacts, hashes, errors):
    try:
        path = inside(root, directory / name)
        if path.exists():
            value = run_files.read_json(path)
            if not isinstance(value, dict):
                raise ValueError("object required")
            artifacts[name] = value
            hashes[name] = sha256_file(path)
    except (ValueError, TypeError, OSError):
        errors.append("invalid_artifact")


def _expected(root, fp, errors):
    try:
        name = f"configs/splits/{fp['set']}.json"
        path = inside(root, name)
        if not path.exists() or sha256_file(path) != fp["files"].get(name):
            return None
        plan = read_split_plan(path)
        if plan.set != fp["set"] or check_split_plan(plan):
            raise ValueError("split identity")
        return plan
    except (ValueError, TypeError, KeyError, OSError):
        errors.append("invalid_split_evidence")
        return None


def read(root, run_dir):
    """누락은 보존하고 읽기 오류는 고정 코드만 남긴다. 현재 코드와 비교하지 않는다."""
    directory = inside(root, run_dir)
    artifacts, hashes, errors, stages = {}, {}, [], []
    for name in FILES:
        _json(root, directory, name, artifacts, hashes, errors)
    fp = artifacts.get("fingerprint.json", {})
    plan = _expected(root, fp, errors) if fp else None
    names = ("dev", "test", "extra") if fp.get("set") == "fc_call_decision" else ("dev", "test")
    for stage in names:
        for kind in ("replay", "derived"):
            _json(root, directory, f"{stage}/{kind}.json", artifacts, hashes, errors)
        expected = None if plan is None else (plan.extra if stage == "extra" else
                    [plan.representative[g] for g in getattr(plan, stage)])
        finals, warnings, present = [], [], False
        try:
            path = inside(root, directory / stage / "final.jsonl")
            present = path.exists()
            finals, warnings = records.read_finals(path)
            if present:
                hashes[f"{stage}/final.jsonl"] = sha256_file(path)
        except (ValueError, TypeError, OSError):
            errors.append("invalid_final_records")
        stages.append(HistoryStage(stage, present, finals, expected, warnings))
    task = None
    if fp:
        try:
            name = fp["inputs"]["task_path"]
            path = inside(root, name)
            if path.exists() and sha256_file(path) == fp["files"].get(name):
                task = load_taskspec(path)
        except (ValueError, TypeError, KeyError, OSError):
            errors.append("invalid_task_evidence")
    return History(directory, artifacts, hashes, stages, errors, task)


def variants(root, results, model, run_id):
    """실제 폴더만 열거한다. 요청한 식별자는 경로 전에 검증한다."""
    from jeveval.io.paths import identifier
    base = inside(root, Path(results) / identifier(model) / identifier(run_id) / "A")
    return [inside(root, path) for path in sorted(base.glob("*/*")) if path.is_dir()]
