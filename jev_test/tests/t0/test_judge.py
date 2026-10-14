"""무엇: T0 전체 분모/우선순위/해시 사슬 · 입력: 합성 관측 · 출력: 누락/위반/정상 · 계약 T-a/f/g."""

from dataclasses import replace
import json

import pytest

from jeveval.t0.judge import judge
from jeveval.t0.request import build_request


def evaluate(cases, refs, servers, tolerances, **kwargs):
    return judge(cases, refs, servers, tolerances, inputs_sha256="a" * 64,
                 reference_epsilon=kwargs.pop("reference_epsilon", 5e-5),
                 server_epsilon=kwargs.pop("server_epsilon", 5e-5), **kwargs)


def test_complete_denominator_and_raw_counts(scenario):
    case, obs, tolerances = scenario
    result = evaluate([case], [obs], [obs], tolerances)
    assert (result.status, result.n_expected_cases, result.n_expected_questions) == ("PASS", 1, 3)
    assert (result.n_compared, result.n_failed, result.n_changed) == (3, 0, 0)
    assert result.max_abs_diff == 0
    raw = json.loads(obs.response_raw)
    raw["answers"]["pick"].update(choice="C", confidence=.0001)
    wrong = replace(obs, response_raw=json.dumps(raw))
    result = evaluate([case], [obs], [wrong], tolerances)
    assert (result.status, result.n_changed, result.n_allowed, result.n_violated) == ("FAIL", 1, 0, 1)


@pytest.mark.parametrize("score, delta, changed, status", [
    (2.0003, .0006, False, "PASS"),
    (2.0009, .0012, True, "FAIL"),
], ids=["within_score_tolerance", "outside_score_tolerance"])
def test_score_change_and_violation_counts(scenario, score, delta, changed, status):
    case, obs, tolerances = scenario
    raw = json.loads(obs.response_raw)
    grade = raw["answers"]["grade"]
    grade.update(score=score, confidence=.2001)
    grade["probabilities"].update({"0":.1999, "4":.2001})
    # 두 score 모두 응답 검증을 통과한다. 분포는 허용폭 안에 두어 score 정책만 검사한다.
    server = replace(obs, response_raw=json.dumps(raw))
    result = evaluate([case], [obs], [server], tolerances)
    row = next(q for q in result.cases[0].questions if q.question_id == "grade")
    limit = sum(range(len(grade["probabilities"]))) * tolerances["mixed"]["grade"].tol_prob + 2 * 5e-5
    assert limit == pytest.approx(.0011)
    assert (delta > limit) is changed
    assert row.score_diff == pytest.approx(delta)
    assert row.distribution_ok is True
    assert row.argmax_changed is True
    assert row.answer_changed is changed
    assert row.change_allowed is (not changed)
    assert row.status == result.cases[0].status == result.status == status
    assert (result.n_compared, result.n_failed) == (3, 0)
    assert (result.n_changed, result.n_allowed, result.n_violated) == (int(changed), 0, int(changed))


def test_fail_beats_missing_reference_and_other_timeout(scenario):
    case, obs, tolerances = scenario
    second = replace(case, case_id="missing")
    bad = replace(obs, response_raw='{"answers":{}}')
    result = evaluate([case, second], [], [bad], tolerances)
    assert result.status == "FAIL"
    assert (result.n_expected_questions, result.n_failed, result.n_compared) == (6, 6, 0)


@pytest.mark.parametrize("side", ["reference", "server"])
def test_missing_and_transport_stay_in_denominator(scenario, side):
    case, obs, tolerances = scenario
    for absent in ([], [replace(obs, transport_error="timeout")], [replace(obs, http_status=503)]):
        refs, servers = (absent, [obs]) if side == "reference" else ([obs], absent)
        result = evaluate([case], refs, servers, tolerances)
        assert (result.status, result.n_expected_questions, result.n_failed) == ("INCOMPLETE", 3, 3)


def test_partial_only_no_reference_and_does_not_mask_failures(scenario):
    case, obs, tolerances = scenario
    assert evaluate([case], [], [obs], tolerances).status == "INCOMPLETE"
    assert evaluate([case], [], [obs], {}, has_reference=False).status == "PARTIAL"
    bad = replace(obs, response_raw="invalid")
    assert evaluate([case], [], [bad], {}, has_reference=False).status == "FAIL"
    assert evaluate([case], [], [], {}, has_reference=False).status == "INCOMPLETE"


@pytest.mark.parametrize("key", ["inputs_sha256", "request_sha256", "envelope_sha256"])
@pytest.mark.parametrize("side", ["reference", "server"])
def test_hash_mismatch_is_error(scenario, key, side):
    case, obs, tolerances = scenario
    bad = replace(obs, **{key:"b" * 64})
    refs, servers = ([bad], [obs]) if side == "reference" else ([obs], [bad])
    with pytest.raises(ValueError, match="hash"):
        evaluate([case], refs, servers, tolerances)


def test_alias_envelopes_share_identity(scenario):
    case, obs, tolerances = scenario
    ref = build_request("served", "private state", {"kind":"plain_text"}, case.request.body["questions"],
                        reference_names={"served":"jev-latest"})
    case = replace(case, reference_envelope_sha256=ref.envelope_sha256)
    reference = replace(obs, envelope_sha256=ref.envelope_sha256)
    assert evaluate([case], [reference], [obs], tolerances).status == "PASS"


def test_duplicate_unknown_empty_and_mutated_expected(scenario):
    case, obs, tolerances = scenario
    for cases, refs, servers in (([case, case], [obs], [obs]), ([case], [obs, obs], [obs]),
                                ([case], [obs], [obs, obs]), ([], [], []),
                                ([case], [obs], [replace(obs, case_id="unknown")])):
        with pytest.raises(ValueError):
            evaluate(cases, refs, servers, tolerances)
    case.request.body["state"] = "mutated"
    with pytest.raises(ValueError, match="hash"):
        evaluate([case], [obs], [obs], tolerances)


def test_unknown_rounding_and_tolerance(scenario):
    case, obs, tolerances = scenario
    assert evaluate([case], [obs], [obs], tolerances, reference_epsilon=None).status == "INCOMPLETE"
    assert evaluate([case], [obs], [obs], tolerances, server_epsilon=None).status == "INCOMPLETE"
    assert evaluate([case], [obs], [obs], {}).status == "INCOMPLETE"
