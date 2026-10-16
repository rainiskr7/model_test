"""T0 순수 자료형의 JSON 왕복과 메모리 전용 객체 경계."""

import pytest

from jeveval.types import Validated
from jeveval.types.t0 import (T0Boundary, T0Case, T0CaseResult, T0Judgement, T0Observation,
    T0QuestionComparison, T0Request, T0Tolerance, T0Variant)
from tests.types.record_support import check_memory_record, check_record


def records():
    comparison = T0QuestionComparison("q", "PASS", 0., False, True, True)
    case = T0CaseResult("c", "PASS", 1, 1, 0, [comparison])
    return [comparison, case, T0Boundary([100], 100, "reject"),
        T0Tolerance("measured_zero", "PASS", 0., .0001, ["batch_1"], 5),
        T0Observation("c", "i", "r", "e", 200, "{}"),
        T0Judgement("PASS", 1, 1, 1, 0, 0, 0, 0, 0., [case])]


@pytest.mark.parametrize("record", records(), ids=lambda r: type(r).__name__)
def test_t0_json_record_boundaries(record):
    check_record(record)


@pytest.mark.parametrize("kind", ["request", "case", "variant"])
def test_t0_memory_record_boundaries(kind):
    request = T0Request({}, b"{}", "e", "r", 0)
    record = {"request": request, "case": T0Case("c", request, "f"),
        "variant": T0Variant("batch_1", 0, {"q": "h"}, Validated(None, [], {}))}[kind]
    check_memory_record(record)


def test_judgement_restores_nested_results_and_defaults():
    result = records()[-1]
    restored = T0Judgement.from_dict(result.to_dict())
    assert isinstance(restored.cases[0], T0CaseResult)
    assert isinstance(restored.cases[0].questions[0], T0QuestionComparison)
    assert restored.cases[0].reasons == [] and restored.cases[0].boundary is False
