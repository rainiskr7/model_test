"""무엇: 보정 반복/변형 완전성 · 입력: 합성 참조 변동 · 출력: 0/미측정/불안정 · 계약 T-d/e."""

from dataclasses import replace

import pytest

from jeveval.t0.tolerance import measure, REPEATS, VARIANTS
from jeveval.types import Validated
from jeveval.types.t0 import T0Variant

QUESTIONS = {"q":{"type":"noul"}, "stable":{"type":"noul"}}
TARGETS = {"q":"a" * 64, "stable":"b" * 64}


def samples(family, delta=0):
    result = []
    for variant in VARIANTS[family]:
        for repeat in range(REPEATS):
            value = .5 + (delta if variant == VARIANTS[family][-1] else 0)
            response = Validated(None, [], {"q":{"type":"noul", "noul":value},
                                             "stable":{"type":"noul", "noul":.6}})
            result.append(T0Variant(variant, repeat, dict(TARGETS), response))
    return result


def run(rows, family="clef", **kwargs):
    return measure(QUESTIONS, rows, family=family, epsilon_r=kwargs.pop("epsilon_r", 5e-5),
                   target_sha256=TARGETS, batch_one_equal=kwargs.pop("batch_one_equal", True), **kwargs)


@pytest.mark.parametrize("family", list(VARIANTS))
def test_zero_and_per_question_variation(family):
    assert REPEATS == 5
    zero = run(samples(family), family)
    assert zero["q"].measurement == "measured_zero" and zero["q"].tol_prob == .0001
    result = run(samples(family, .001), family)
    assert result["q"].measurement == "measured"
    assert result["q"].variation == pytest.approx(.001)
    assert result["q"].tol_prob == pytest.approx(.002)
    assert result["stable"].tol_prob == .0001


@pytest.mark.parametrize("delta,status", [(.02,"PASS"), (.020001,"INCOMPLETE")])
def test_unstable_threshold(delta, status):
    result = run(samples("clef", delta))["q"]
    assert result.status == status
    if status == "INCOMPLETE":
        assert result.measurement == "measured" and result.tol_prob is None


def test_missing_failed_and_changed_target_not_zero():
    rows = samples("clef")
    assert run(rows[:-1])["q"].measurement == "unmeasured"
    assert run(rows, epsilon_r=None)["q"].reason == "unknown_rounding"
    assert run(rows, batch_one_equal=False)["q"].reason == "batch_one_not_verified"
    bad = replace(rows[-1], response=Validated("bad_body", [], None))
    assert run(rows[:-1] + [bad])["q"].reason == "reference_failure"
    bad = replace(rows[-1], target_sha256={**TARGETS, "q":"c" * 64})
    assert run(rows[:-1] + [bad])["q"].reason == "target_mismatch"
    result = run(samples("pplx_v1_1"), "pplx_v1_1", batch_one_equal=False)
    assert result["q"].status == "PASS"


def test_duplicate_or_unknown_variant_is_error():
    rows = samples("clef")
    for modified in (rows + [rows[0]], [replace(rows[0], repeat=True)],
                     [replace(rows[0], variant="permuted_questions")]):
        with pytest.raises(ValueError):
            run(modified)


def test_unrounded_measured_zero_is_exact():
    result = run(samples("pplx_v1"), "pplx_v1", epsilon_r=0)
    assert result["q"].tol_prob == 0 and result["q"].measurement == "measured_zero"
