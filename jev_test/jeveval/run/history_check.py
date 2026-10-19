"""무엇: 역사 증거 검사 · 입력: History · 출력: HistoryCheck · 계약 §5-1b; 순수."""

from collections import Counter
from datetime import datetime
from pathlib import PurePosixPath
import re

from jeveval.types import ScoreTable, ThresholdFile
from jeveval.run.history_statistics import validate
from jeveval.types.history import HistoryCheck, StageCheck

IDENTITY = ("model", "set", "variant", "run_id")


def _fingerprint(history, fp):
    if fp.get("schema") != "fingerprint/1":
        raise ValueError("fingerprint schema")
    if any(not isinstance(fp.get(k), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", fp[k])
           for k in IDENTITY):
        raise ValueError("fingerprint identity")
    if not re.fullmatch(r"[0-9a-f]{64}", fp.get("code_sha256", "")) or not fp.get("started_at"):
        raise ValueError("fingerprint provenance")
    if history.task is not None and (history.task.set, history.task.variant) != (fp["set"], fp["variant"]):
        raise ValueError("frozen task identity")
    if datetime.fromisoformat(fp["started_at"].replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("fingerprint time")
    if fp.get("dataset_verified") is not True or not isinstance(fp["files"], dict) or not fp["files"]:
        raise ValueError("fingerprint evidence")
    for name, digest in fp["files"].items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != name:
            raise ValueError("fingerprint file path")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("fingerprint file digest")
    inputs = fp["inputs"]
    if any(inputs[k] != fp[k] for k in ("set", "variant", "run_id")):
        raise ValueError("input identity")
    if inputs["task_path"] not in fp["files"] or inputs["model_cfg_path"] not in fp["files"]:
        raise ValueError("input file identity")
    if tuple(history.directory.parts[-5:]) != (fp["model"], fp["run_id"], "A", fp["set"], fp["variant"]):
        raise ValueError("directory identity")


def _artifacts(history, fp):
    a, h = history.artifacts, history.hashes
    for name in ("threshold.json", "risk.json", "scores.json", "question_risk.json"):
        if name in a and any(a[name].get(k) != fp[k] for k in IDENTITY):
            raise ValueError("result identity")
    if "threshold.json" in a:
        threshold = ThresholdFile.from_dict(a["threshold.json"])
        if threshold.schema != "threshold/1":
            raise ValueError("threshold schema")
    if "scores.json" in a and ScoreTable.from_dict(a["scores.json"]).schema != "scores/1":
        raise ValueError("scores schema")
    if "risk.json" in a:
        risk = a["risk.json"]
        if risk.get("schema") != "risk/1" or set(risk["cells"]) != {"0.01", "0.02", "0.05"}:
            raise ValueError("risk schema")
        if "threshold.json" in h and risk["threshold_sha256"] != h["threshold.json"]:
            raise ValueError("risk threshold hash")
    if "test/seal.json" in a:
        for key, name in (("threshold_sha256", "threshold.json"), ("dev_final_sha256", "dev/final.jsonl")):
            if name in h and a["test/seal.json"][key] != h[name]:
                raise ValueError("seal hash")
    if "summary.json" in a:
        summary = a["summary.json"]
        if summary.get("model") != fp["model"] or summary.get("benchmark") != f"jev:{fp['set']}:{fp['variant']}":
            raise ValueError("summary identity")
        if "run_id" in summary and summary["run_id"] != fp["run_id"]:
            raise ValueError("summary run identity")


def _origins(history, fp):
    """파생 출처 연결을 검사하되 자유 경로·reason은 공개 결과로 넘기지 않는다."""
    for stage in history.stages:
        marker = history.artifacts.get(f"{stage.name}/derived.json")
        origin = None if marker is None else marker["derived_from"]
        if any(f.derived_from != origin for f in stage.finals):
            raise ValueError("derived provenance differs")
        if origin is not None:
            path = PurePosixPath(origin)
            if path.is_absolute() or ".." in path.parts or path.as_posix() != origin:
                raise ValueError("derived source path")
            if path.parts[-5:] != (fp["model"], fp["run_id"], "A", fp["set"], "full"):
                raise ValueError("derived source identity")
        replay = history.artifacts.get(f"{stage.name}/replay.json")
        if replay is not None:
            if replay.get("schema") != "replay/1" or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", replay["source_run_id"]):
                raise ValueError("replay identity")
            for name in ("source_code_sha256", "source_attempts_sha256", "source_fingerprint_sha256"):
                if not re.fullmatch(r"[0-9a-f]{64}", replay[name]):
                    raise ValueError("replay digest")


def _stage(stage):
    ids = [f.logical_id for f in stage.finals]
    if len(set(ids)) != len(ids) or any(f.status not in ("ok", "error", "rejected", "truncated") for f in stage.finals):
        raise ValueError("invalid stage records")
    expected = None if stage.expected is None else set(stage.expected)
    if expected is not None and not set(ids) <= expected:
        raise ValueError("unexpected final ID")
    complete = stage.present and expected is not None and set(ids) == expected and not stage.warnings
    return StageCheck(stage.name, "verified_complete" if complete else "incomplete",
                      None if expected is None else len(expected), len(ids),
                      None if expected is None else len(expected - set(ids)), dict(Counter(f.status for f in stage.finals)))


def check(history):
    """손상이 누락보다 우선한다. summary는 비주판에서 원래 생성되지 않으므로 선택적이다."""
    errors, stages = list(history.errors), []
    fp = history.artifacts.get("fingerprint.json")
    try:
        if fp is not None:
            _fingerprint(history, fp)
            _artifacts(history, fp)
            _origins(history, fp)
            validate(history.artifacts, history.hashes)
        stages = [_stage(stage) for stage in history.stages]
        risk = history.artifacts.get("risk.json")
        for stage in stages:
            if risk is not None and stage.status == "verified_complete" and stage.name in ("dev", "test"):
                if any(cell[stage.name]["n_groups"] != stage.finalized for cell in risk["cells"].values()):
                    raise ValueError("risk stage count mismatch")
    except (ValueError, TypeError, KeyError, AttributeError):
        errors.append("evidence_mismatch")
    if errors:
        return HistoryCheck("damaged", sorted(set(errors)), stages)
    required = {"fingerprint.json", "threshold.json", "risk.json", "scores.json", "test/seal.json"}
    complete = required <= history.artifacts.keys() and all(s.status == "verified_complete" for s in stages)
    return HistoryCheck("verified_complete" if complete else "incomplete", [], stages)
