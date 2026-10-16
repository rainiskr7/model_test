"""무엇: T0 상태 우선순위 · 입력: 상태 목록/참조 유무 · 출력: 합성 상태/오류 · 계약 §8-7 T-g."""

import pytest

from jeveval.t0.status import status_of


@pytest.mark.parametrize("statuses,expected", [
    pytest.param([], "PASS", id="empty"),
    pytest.param(["PASS"], "PASS", id="pass"),
    pytest.param(["PARTIAL"], "PASS", id="reference-controls-partial"),
    pytest.param(["PASS", "INCOMPLETE"], "INCOMPLETE", id="incomplete-over-pass"),
    pytest.param(["PASS", "FAIL"], "FAIL", id="fail-over-pass"),
    pytest.param(["PASS", "INCOMPLETE", "FAIL"], "FAIL", id="fail-over-incomplete"),
])
@pytest.mark.parametrize("has_reference", [True, False])
def test_status_priority_and_reference_presence(statuses, expected, has_reference):
    if not has_reference and expected == "PASS":
        expected = "PARTIAL"
    assert status_of(statuses, has_reference=has_reference) == expected
    assert status_of(reversed(statuses), has_reference=has_reference) == expected


@pytest.mark.parametrize("unknown", ["UNKNOWN", "fail", "", None])
def test_unknown_status_rejected_even_with_failure(unknown):
    with pytest.raises(ValueError, match="^invalid T0 status$"):
        status_of(["FAIL", unknown])
