"""무엇: 실행 공유 타입 왕복 · 입력: 합성 계획·집계 · 출력: frozen·중첩 사본 · 계약 §8-5·§8-6."""

from dataclasses import FrozenInstanceError

import pytest

from jeveval.types import CallPlan, Decision, JsonRecord, Rendered, Request, RunSummary


@pytest.mark.parametrize("value", [Decision(True, None), Decision(False, 1.0),
                                  RunSummary(2, 1, 3, 2, 1, {"ok": 2})])
def test_json_records(value):
    data = value.to_dict()
    assert type(value).from_dict(data) == value
    if isinstance(value, RunSummary):
        data["by_status"]["ok"] = 0
        assert value.by_status == {"ok": 2}
    with pytest.raises(FrozenInstanceError):
        value.extra = 0


def test_call_plan_is_memory_only():
    plan = CallPlan("s:g:i", "s:g:i", "systemone", ["q"], {"q": "noul"}, b"{}", "a" * 64,
                    Request("m", "state", {}), None, Rendered("state", 5), [])
    assert not isinstance(plan, JsonRecord) and plan.body == b"{}"
    with pytest.raises(FrozenInstanceError):
        plan.body = b"changed"


def test_deferred_summary_roundtrip():
    summary = RunSummary(5, 1, 2, 0, 1, {"ok": 1}, 3)
    assert summary.n_deferred == 3
    assert RunSummary.from_dict(summary.to_dict()) == summary
