"""무엇: T0 분포/답 정책 대조 · 입력: 검증된 요청별 답/허용폭 · 출력: T0CaseResult · 계약 §8-7 T-f."""

from jeveval.t0.distribution import nonnegative, status_of, vector, within
from jeveval.types import Validated
from jeveval.types.t0 import T0CaseResult, T0QuestionComparison, T0Tolerance


def _answer(question, reference, server, tolerance, epsilon_r):
    kind = question["type"]
    if kind == "noul":
        changed = (reference["noul"] >= .5) != (server["noul"] >= .5)
        return changed, not changed or within(abs(reference["noul"] - .5), tolerance), None, None
    if kind == "choice":
        changed = reference["choice"] != server["choice"]
        probs = reference["probabilities"]
        allowed = within(max(probs.values()) - probs[server["choice"]], 2 * tolerance)
        return changed, allowed, None, None
    delta = abs(server["score"] - reference["score"])
    ref, srv = vector(question, reference), vector(question, server)
    argmax_changed = ref.index(max(ref)) != srv.index(max(srv))
    allowed = within(delta, sum(range(len(ref))) * tolerance + 2 * epsilon_r)
    # score 는 이산 답이 없다: 허용폭 밖으로 움직인 경우만 변경(=위반)으로 센다 (§8-7 T-f).
    return not allowed, allowed, delta, argmax_changed


def compare_question(qid, question, reference, server, tolerance: T0Tolerance, epsilon_r):
    ref, srv = vector(question, reference), vector(question, server)
    diff = max(abs(a - b) for a, b in zip(ref, srv, strict=True))
    ready = (tolerance.status == "PASS" and tolerance.measurement in ("measured", "measured_zero")
             and nonnegative(tolerance.tol_prob) and nonnegative(epsilon_r))
    # 미측정 때도 원시 변경은 기록하되 허용/위반으로 판정하지 않는다.
    changed, allowed, score_diff, argmax_changed = _answer(
        question, reference, server, tolerance.tol_prob if ready else 0, epsilon_r if ready else 0)
    distribution_ok = within(diff, tolerance.tol_prob) if ready else None
    status = ("PASS" if distribution_ok and allowed else "FAIL") if ready else "INCOMPLETE"
    return T0QuestionComparison(qid, status, diff, changed, allowed if ready else None,
                                distribution_ok, score_diff, argmax_changed)


def invalid_result(case_id, count, reference: Validated, server: Validated):
    """서버 계약 위반은 참조 실패/미확인 정책보다 우선하며 요청 전체를 실패로 센다."""
    reasons = []
    if reference.reason:
        reasons.append("reference_" + reference.reason)
    if server.reason:
        reasons.append("server_" + server.reason)
    if not reasons:
        return None
    status = "FAIL" if server.reason and server.reason != "unknown_rounding" else "INCOMPLETE"
    return T0CaseResult(case_id, status, count, 0, count, reasons=reasons)


def compare_request(case_id, questions, reference: Validated, server: Validated,
                    tolerances: dict[str, T0Tolerance], epsilon_r):
    """입력은 검증기 결과다. 한 답이라도 검증 실패하면 모든 질문을 비교하지 않는다."""
    invalid = invalid_result(case_id, len(questions), reference, server)
    if invalid is not None:
        return invalid
    if reference.answers is None or server.answers is None:
        raise ValueError("validated answers required")
    if reference.answers.keys() != questions.keys() or server.answers.keys() != questions.keys():
        raise ValueError("comparison question IDs differ")
    missing = T0Tolerance("unmeasured", "INCOMPLETE", None, None, [], 5, "missing_tolerance")
    rows = [compare_question(qid, q, reference.answers[qid], server.answers[qid],
                             tolerances.get(qid, missing), epsilon_r) for qid, q in questions.items()]
    return T0CaseResult(case_id, status_of(r.status for r in rows), len(questions), len(rows), 0, rows)
