"""무엇: 보조 보고 검증 조립 · 입력: 역사/주 상태 · 출력: 독립 보조 절 · 계약 §7-4c·7-4d."""

from dataclasses import replace

from jeveval.io import analysis_artifacts, run_files, variant_policy
from jeveval.io.paths import inside
from jeveval.run import history_stage, variant_calculation, variant_registration
from jeveval.score.power import power_table
from jeveval.types.report import ReportSelective, ReportScoreVariants


def attach(root, saved, result):
    """보조 손상으로 주 판정이나 질문 등록 지위를 변경하지 않는다."""
    if result.status != "verified_complete":
        return result
    aux = saved.aux.get("selective", dict(status="missing", value=None))
    selective = ReportSelective(aux["status"], aux["value"], power_table(saved.artifacts["risk.json"]))
    return replace(result, selective=selective, score_variants=_variants(root, saved))


def _variants(root, saved):
    if any(f.derived_from is not None for s in saved.stages for f in s.finals):
        return ReportScoreVariants("unsupported", {}, "파생 변형: 확신 변형 역사 분석 미지원")
    try:
        path = inside(root, saved.directory / "score_variants.json")
        if not run_files.exists(path):
            return ReportScoreVariants("missing", {}, "확신 변형 보조 지표 없음")
        value = run_files.read_json(path)
        fp = saved.artifacts["fingerprint.json"]
        if value["schema"] != "score_variants/1" or any(value[k] != fp[k] for k in variant_registration.IDENTITY):
            raise ValueError("variant report identity")
        if value["inputs"] != {p: saved.hashes[p] for p in ("dev/final.jsonl", "test/final.jsonl")}:
            raise ValueError("variant report inputs")
        stages = {s: history_stage.restore(root, saved, s) for s in ("dev", "test")}
        policy = variant_calculation.development(stages["dev"])
        status = value["registration"]["status"]
        if status == "registered":
            e = analysis_artifacts.read(root, saved.directory)
            if variant_registration.check(e, policy) != "registered":
                raise ValueError("variant registration damaged")
            manifest, digest = e["manifest"], e["manifest_sha256"]
            policy = e["artifacts"]["variant_threshold.json"]
        elif status == "exploratory":
            manifest, digest = variant_policy.MANIFEST, variant_policy.policy(root)[1]
        else:
            raise ValueError("variant registration damaged")
        if value["registration"] != dict(status=status, manifest=manifest, manifest_sha256=digest):
            raise ValueError("variant policy changed")
        calculated = variant_calculation.trial(stages["test"], policy)
        if value["cells"] != calculated:
            raise ValueError("variant report calculation")
        return ReportScoreVariants(status, calculated)
    except (ValueError, KeyError, TypeError, OSError, AttributeError):
        return ReportScoreVariants("registration_damaged", {}, "확신 변형 검증 실패 — 수치 비공개")
