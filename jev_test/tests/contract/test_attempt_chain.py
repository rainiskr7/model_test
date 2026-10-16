"""무엇: 시도 체인 구조 검사 · 입력: 메모리의 AttemptRecord 목록 · 출력: 통과/정확한 오류 · 계약 §5-3·§8-1."""

from dataclasses import replace

import pytest

from jeveval.contract.attempt_chain import check_attempt_chain
from tests.types.samples import attempt as sample_attempt


def attempt(**changes):
    return replace(sample_attempt(), **{"terminal": False, **changes})


@pytest.mark.parametrize("rows,message", [
    pytest.param([attempt(), attempt()],
        "line 2: duplicate or nonconsecutive attempt", id="duplicate"),
    pytest.param([attempt(attempt=2)],
        "line 1: duplicate or nonconsecutive attempt", id="missing-first"),
    pytest.param([attempt(), attempt(attempt=3)],
        "line 2: duplicate or nonconsecutive attempt", id="gap"),
    pytest.param([attempt(terminal=True), attempt(attempt=2)],
        "line 2: attempt after terminal or changed call identity", id="after-terminal"),
    pytest.param([attempt(terminal=True), attempt(attempt=2, terminal=True)],
        "line 2: attempt after terminal or changed call identity", id="two-terminals"),
    pytest.param([attempt(), attempt(attempt=2, logical_id="changed")],
        "line 2: attempt after terminal or changed call identity", id="logical-id-changed"),
    pytest.param([attempt(), attempt(attempt=2, request_sha256="b" * 64)],
        "line 2: attempt after terminal or changed call identity", id="request-changed"),
])
def test_attempt_invariants_report_exact_line_and_message(rows, message):
    with pytest.raises(ValueError) as error:
        check_attempt_chain(rows)
    assert str(error.value) == message


@pytest.mark.parametrize("rows", [
    pytest.param([], id="empty"),
    pytest.param([attempt()], id="unfinished"),
    pytest.param([attempt(), attempt(attempt=2, terminal=True)], id="terminal"),
    pytest.param([attempt(), attempt(call_id="other", logical_id="other-id",
        request_sha256="b" * 64, terminal=True), attempt(attempt=2, terminal=True)], id="interleaved"),
    pytest.param([attempt(attempt=i) for i in range(1, 7)], id="budget-belongs-to-run"),
])
def test_valid_attempt_chains_pass(rows):
    assert check_attempt_chain(rows) is None


def test_interleaved_error_uses_global_record_line():
    rows = [attempt(), attempt(call_id="other", terminal=True), attempt(attempt=3)]
    with pytest.raises(ValueError) as error:
        check_attempt_chain(rows)
    assert str(error.value) == "line 3: duplicate or nonconsecutive attempt"
