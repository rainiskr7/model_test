"""무엇: T0 기대 집합/해시 사슬/상태 결합 · 입력: 확정 요청·관측·허용폭 · 출력: T0Judgement · 계약 §8-7 T-f/g."""

from hashlib import sha256

from jeveval.t0.boundary import judge_boundary
from jeveval.t0.compare import compare_request
from jeveval.t0.status import status_of
from jeveval.t0.request import canonical_bytes
from jeveval.t0.response import validate_response
from jeveval.types.t0 import T0CaseResult, T0Judgement


def _index(rows, expected=None):
    result = {}
    for row in rows:
        if not row.case_id or row.case_id in result:
            raise ValueError("duplicate/empty case ID")
        if expected is not None and row.case_id not in expected:
            raise ValueError("unexpected case ID")
        result[row.case_id] = row
    return result


def _chain(case, observation, inputs_sha256, reference=False):
    request = case.request
    identity = {k: request.body[k] for k in ("state", "questions")}
    identity["images"] = request.body.get("images", [])
    if (request.envelope_bytes != canonical_bytes(request.body)
            or request.envelope_sha256 != sha256(request.envelope_bytes).hexdigest()
            or request.request_sha256 != sha256(canonical_bytes(identity)).hexdigest()):
        raise ValueError("expected request hash mismatch")
    envelope = case.reference_envelope_sha256 if reference else request.envelope_sha256
    if (observation.inputs_sha256 != inputs_sha256 or observation.request_sha256 != request.request_sha256
            or observation.envelope_sha256 != envelope):
        raise ValueError("T0 request hash chain mismatch")


def _unavailable(observation):
    return observation.transport_error is not None or observation.http_status is None or observation.http_status >= 500


def _case(case, reference, server, tolerances, reference_epsilon, server_epsilon, has_reference):
    questions = case.request.body["questions"]
    count = len(questions)
    def result(status, reason):
        return T0CaseResult(case.case_id, status, count, 0, count, reasons=[reason], boundary=case.boundary is not None)
    if server is None or _unavailable(server):
        return result("INCOMPLETE", "server_unavailable")
    if case.boundary is not None:
        status = judge_boundary(case.boundary, server)
        if server.http_status == 200:
            valid = validate_response(server.response_raw, questions, server_epsilon)
            if valid.reason:
                status = status_of([status, "INCOMPLETE" if valid.reason == "unknown_rounding" else "FAIL"])
        return T0CaseResult(case.case_id, status, count, 0, count if status != "PASS" else 0,
                            reasons=[] if status == "PASS" else ["boundary_" + status.lower()], boundary=True)
    if server.http_status != 200:
        return result("FAIL", "server_http_contract")
    srv = validate_response(server.response_raw, questions, server_epsilon)
    if srv.reason:
        return result("INCOMPLETE" if srv.reason == "unknown_rounding" else "FAIL", "server_" + srv.reason)
    if not has_reference:
        return T0CaseResult(case.case_id, "PARTIAL", count, 0, 0)
    if reference is None or _unavailable(reference) or reference.http_status != 200:
        return result("INCOMPLETE", "reference_unavailable")
    ref = validate_response(reference.response_raw, questions, reference_epsilon)
    epsilon = None if reference_epsilon is None or server_epsilon is None else max(reference_epsilon, server_epsilon)
    return compare_request(case.case_id, questions, ref, srv, tolerances, epsilon)


def judge(expected, references, servers, tolerances, *, inputs_sha256, reference_epsilon,
          server_epsilon, has_reference=True):
    """중복/낯선 ID·해시 불일치는 오류, 누락은 기대 분모에 남겨 INCOMPLETE로 센다."""
    cases = _index(expected)
    if not cases:
        raise ValueError("expected cases must not be empty")
    ref, srv = _index(references, cases), _index(servers, cases)
    results = []
    for cid, case in cases.items():
        if not case.request.body["questions"]:
            raise ValueError("expected questions must not be empty")
        for records, is_reference in ((ref, True), (srv, False)):
            if cid in records:
                _chain(case, records[cid], inputs_sha256, is_reference)
        results.append(_case(case, ref.get(cid), srv.get(cid), tolerances.get(cid, {}),
                             reference_epsilon, server_epsilon, has_reference))
    rows = [q for case in results for q in case.questions]
    return T0Judgement(status_of((r.status for r in results), has_reference=has_reference),
        len(cases), sum(r.n_expected for r in results), sum(r.n_compared for r in results),
        sum(r.n_failed for r in results), sum(q.answer_changed for q in rows),
        sum(q.answer_changed and q.change_allowed is True for q in rows),
        sum(q.answer_changed and q.change_allowed is False for q in rows),
        max((q.max_abs_diff for q in rows), default=None), results)
