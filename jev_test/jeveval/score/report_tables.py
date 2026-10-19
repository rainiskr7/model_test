"""무엇: 공개 표 투영 · 입력: 파일 schema/검사 결과 · 출력: ReportVariant · 계약 §7-6; 순수."""

from dataclasses import replace
from datetime import datetime
from itertools import combinations
import re

from jeveval.score.threshold import TAUS
from jeveval.types.report import CommonErrors, ReplayOrigin, ReportQuestion, ReportRisk, ReportVariant


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ValueError("invalid public identifier")
    return value


def digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("invalid public digest")
    return value


def _questions(scores):
    result = []
    for qid, q in scores["populations"]["test"]["questions"].items():
        safe_id(qid)
        if q["role"] not in ("success", "diagnostic"):
            raise ValueError("invalid question role")
        positive = q["classes"].get("true", {}) if q["type"] == "noul" else {}
        support = positive.get("support", 0) if q["type"] == "noul" else None
        result.append(ReportQuestion(qid, q["role"], q["accuracy"]["num"], q["accuracy"]["den"],
            q["macro_f1"], q["calibration"]["ece"], support,
            positive.get("predicted", 0) if support is not None else None,
            positive.get("tp", 0) if support is not None else None, support is not None and support < 30))
    return result


def variant(history, checked, primary=None):
    parts = history.directory.parts
    model, run_id, _, set_name, name = parts[-5:]
    for value in (model, run_id, set_name, name):
        safe_id(value)
    result = ReportVariant(model, set_name, name, checked.status, checked.reasons, checked.stages, primary=primary)
    if checked.status == "damaged":
        return result
    a, fp = history.artifacts, history.artifacts.get("fingerprint.json")
    if fp is None:
        return result
    try:
        stamp = datetime.fromisoformat(fp["started_at"].replace("Z", "+00:00")).isoformat()
        replay = [ReplayOrigin(stage, safe_id(a[key]["source_run_id"]), digest(a[key]["source_code_sha256"]),
                  digest(a[key]["source_attempts_sha256"])) for stage in ("dev", "test", "extra")
                  if (key := f"{stage}/replay.json") in a]
        result = replace(result, code_sha256=digest(fp["code_sha256"]), started_at=stamp, replay=replay)
        t0 = a.get("summary.json", {}).get("extra", {}).get("t0_status", "unknown")
        result = replace(result, t0_status=t0 if t0 in ("passed", "partial", "not_run") else "unknown")
        if checked.status != "verified_complete":
            return result
        cells = a["risk.json"]["cells"]
        risks = [ReportRisk(tau, cells[tau]["status"], cells[tau]["test"]["n_accepted"],
                 cells[tau]["test"]["n_denom"], cells[tau]["test"]["k_errors"], cells[tau]["test"]["U"],
                 cells[tau]["insufficient_by_design"]) for tau in TAUS]
        if any(r.status not in ("MEETS", "FAILS", "UNDERPOWERED", "NO_THRESHOLD") for r in risks):
            raise ValueError("invalid risk status")
        return replace(result, risk=risks, questions=_questions(a["scores.json"]))
    except (ValueError, TypeError, KeyError, AttributeError):
        return replace(result, status="damaged", reasons=["invalid_public_statistics"], risk=[], questions=[], replay=[])


def common_errors(variants):
    result = []
    for left, right in combinations(variants, 2):
        if (left.set_name, left.variant) != (right.set_name, right.variant) or left.model == right.model:
            continue
        for a in left.decompositions:
            for b in right.decompositions:
                if a.stage != b.stage:
                    continue
                common = set(a.valid_ids) & set(b.valid_ids)
                result.append(CommonErrors(left.model, right.model, left.set_name, left.variant, a.stage,
                    len(common), len(a.valid_ids) - len(common), len(b.valid_ids) - len(common),
                    len(common & set(a.wrong_ids) & set(b.wrong_ids))))
    return result
