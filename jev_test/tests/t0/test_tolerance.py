"""무엇: 보정 반복/변형 완전성 · 입력: 합성 참조 변동 · 출력: 0/미측정/불안정 · 계약 T-d/e."""

from dataclasses import replace

import pytest

from jeveval.t0.tolerance import measure
from jeveval.types import Validated
from jeveval.types.t0 import T0Variant

QUESTIONS = {"q":{"type":"noul"}, "stable":{"type":"noul"}}
TARGETS = {"q":"a" * 64, "stable":"b" * 64}


def samples(family, delta=0, *, policy):
    result = []
    for variant in policy.variants[family]:
        for repeat in range(policy.repeats):
            value = .5 + (delta if variant == policy.variants[family][-1] else 0)
            response = Validated(None, [], {"q":{"type":"noul", "noul":value},
                                             "stable":{"type":"noul", "noul":.6}})
            result.append(T0Variant(variant, repeat, dict(TARGETS), response))
    return result


def run(rows, family="clef", *, policy, **kwargs):
    return measure(QUESTIONS, rows, policy=policy, family=family, epsilon_r=kwargs.pop("epsilon_r", 5e-5),
                   target_sha256=TARGETS, batch_one_equal=kwargs.pop("batch_one_equal", True), **kwargs)


@pytest.mark.parametrize("family", ["clef", "clef_flash", "pplx_v1", "pplx_v1_1"])
def test_zero_and_per_question_variation(family, t0_policy):
    assert t0_policy.repeats == 5
    zero = run(samples(family, policy=t0_policy), family, policy=t0_policy)
    assert zero["q"].measurement == "measured_zero" and zero["q"].tol_prob == .0001
    result = run(samples(family, .001, policy=t0_policy), family, policy=t0_policy)
    assert result["q"].measurement == "measured"
    assert result["q"].variation == pytest.approx(.001)
    assert result["q"].tol_prob == pytest.approx(.002)
    assert result["stable"].tol_prob == .0001


@pytest.mark.parametrize("delta,status", [(.02,"PASS"), (.020001,"INCOMPLETE")])
def test_unstable_threshold(delta, status, t0_policy):
    result = run(samples("clef", delta, policy=t0_policy), policy=t0_policy)["q"]
    assert result.status == status
    if status == "INCOMPLETE":
        assert result.measurement == "measured" and result.tol_prob is None


def test_missing_failed_and_changed_target_not_zero(t0_policy):
    rows = samples("clef", policy=t0_policy)
    assert run(rows[:-1], policy=t0_policy)["q"].measurement == "unmeasured"
    assert run(rows, epsilon_r=None, policy=t0_policy)["q"].reason == "unknown_rounding"
    assert run(rows, batch_one_equal=False, policy=t0_policy)["q"].reason == "batch_one_not_verified"
    bad = replace(rows[-1], response=Validated("bad_body", [], None))
    assert run(rows[:-1] + [bad], policy=t0_policy)["q"].reason == "reference_failure"
    bad = replace(rows[-1], target_sha256={**TARGETS, "q":"c" * 64})
    assert run(rows[:-1] + [bad], policy=t0_policy)["q"].reason == "target_mismatch"
    result = run(samples("pplx_v1_1", policy=t0_policy), "pplx_v1_1", batch_one_equal=False, policy=t0_policy)
    assert result["q"].status == "PASS"


def test_duplicate_or_unknown_variant_is_error(t0_policy):
    rows = samples("clef", policy=t0_policy)
    for modified in (rows + [rows[0]], [replace(rows[0], repeat=True)],
                     [replace(rows[0], variant="permuted_questions")]):
        with pytest.raises(ValueError):
            run(modified, policy=t0_policy)


def test_unrounded_measured_zero_is_exact(t0_policy):
    result = run(samples("pplx_v1", policy=t0_policy), "pplx_v1", epsilon_r=0, policy=t0_policy)
    assert result["q"].tol_prob == 0 and result["q"].measurement == "measured_zero"


def test_custom_repeat_budget_controls_completeness(t0_policy):
    policy = replace(t0_policy, repeats=2)
    rows = samples("clef", policy=policy)
    assert len(rows) == 2 * len(policy.variants["clef"])
    assert run(rows, policy=policy)["q"].status == "PASS"
    missing = run(rows[:-1], policy=policy)["q"]
    assert missing.status == "INCOMPLETE" and missing.measurement == "unmeasured"
    with pytest.raises(ValueError):
        run(rows + [replace(rows[0], repeat=2)], policy=policy)
