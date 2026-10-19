"""무엇: 보고용 등록 검증 조립 · 입력: 역사 증거·질문 통계 · 출력: 안전한 지위 · 계약 판 5 보정 2 §7-4b."""

from jeveval.io import question_registration as evidence_io
from jeveval.run import history_stage, question_registration
from jeveval.score.question_outcomes import observations
from jeveval.score.question_risk import calculate, thresholds


def status(root, saved, value):
    """보고 파일의 registered 문자열만 믿지 않고 봉인과 개발/시험 계산을 확인한다."""
    declared = value.get("registration", {}).get("status")
    if declared == "exploratory":
        return declared
    if declared != "registered":
        return "registration_damaged"
    e = evidence_io.read(root, saved.directory)
    if question_registration.check(e) != "registered":
        return "registration_damaged"
    try:
        stages = {s: history_stage.restore(root, saved, s) for s in ("dev", "test")}
        rows = {s: observations(stages[s].finals, stages[s].items, s) for s in stages}
        if question_registration.check(e, thresholds(rows["dev"])) != "registered":
            return "registration_damaged"
        if (value["registration"]["manifest"] != e["manifest"] or
                value["registration"]["manifest_sha256"] != e["manifest_sha256"]):
            return "registration_damaged"
        calculated = calculate(rows["dev"], rows["test"], e["artifacts"]["question_threshold.json"]["by_question"])
        return "registered" if all(value.get(k) == v for k, v in calculated.items()) else "registration_damaged"
    except (ValueError, OSError, KeyError, TypeError):
        return "registration_damaged"
