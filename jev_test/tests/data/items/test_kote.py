"""무엇: KOTE 항목 검사 · 입력: 합성 과반수 라벨 · 출력: 강등·충돌 · 계약 §6-2."""

from copy import deepcopy
from dataclasses import replace

import pytest

from jeveval.data.items.kote import build_items
from jeveval.types import SourceRow


def test_majority_demotion_and_group_conflicts(settings, plan_for, label_rules):
    task, lists = settings("kote_escalation")
    rows = [SourceRow(task.set, str(i), dict(text=t, labels=[0, 1], labels_majority=labels))
            for i, t, labels in [(0, "same", ["없음"]), (1, "same", []), (2, "next", ["짜증"])]]
    plan = plan_for(rows, task, demotions=["없음"])
    before = deepcopy((rows, task))
    result = build_items(rows, plan, task, lists, label_rules)
    first, second = result["dev"][0], result["test"][0]
    assert first.meta["flags"] == ["label_conflict_group"] and second.meta["flags"] == []
    assert first.questions[-1].role == "diagnostic" and first.questions[-1].gold == "true"
    assert second.questions[-1].gold == "false" and second.questions[2].gold == "true"
    assert first.state_fields == "same" and first.baseline is None
    assert result["extra"] == [] and (rows, task) == before
    with pytest.raises(ValueError, match="demotion"):
        build_items(rows, replace(plan, diagnostic_demotions=["not configured"]), task, lists, label_rules)
