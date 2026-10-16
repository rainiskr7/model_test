"""무엇: K-MHaS 항목·동결 설정 검사 · 입력: 합성 행/설정 · 출력: 순서·충돌·등록 대조 · 계약 §6-2."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from jeveval.contract.b1_prompt import build_b1_call
from jeveval.data.items.kmhas import build_items
from jeveval.io.config import load_taskspec
from jeveval.io.tasks import read_b1_config, read_lists
from jeveval.types import BoundQuestion, Rendered, SourceRow


def _rows():
    return [SourceRow("kmhas", str(i), dict(text=t, label=labels, label_names=names))
            for i, t, labels, names in [(2, "same", [], []), (1, "same", [0], ["origin"]),
                                        (3, "third", [], []), (10, "second", [], [])]]


def test_stage_order_logical_id_conflict_and_detachment(settings, plan_for, label_rules):
    task, lists = settings("kmhas")
    rows = _rows()
    plan = plan_for(rows, task, dev=["1", "10"])
    before = deepcopy((rows, lists))
    result = build_items(rows, plan, task, lists, label_rules)
    assert [f"{i.set}:{i.group_id}:{i.item_id}" for i in result["dev"]] == ["kmhas:1:1", "kmhas:10:10"]
    assert [i.item_id for i in result["test"]] == ["3"] and result["extra"] == []
    item = result["dev"][0]
    assert item.state_fields == "same" and item.questions[0].gold == "true"
    assert item.meta == dict(service=None, stratum=None, flags=["label_conflict_group"])
    assert item.baseline is None
    item.questions[0].criteria.clear()
    assert (rows, lists) == before


@pytest.mark.parametrize("change", ["overlap", "duplicate", "order", "representative", "groups", "extra"])
def test_bad_plan_stops_before_building(settings, plan_for, change, label_rules):
    task, lists = settings("kmhas")
    rows = _rows()
    plan = plan_for(rows, task)
    edits = {"overlap": dict(test=sorted(plan.test + plan.dev)), "duplicate": dict(dev=plan.dev * 2),
             "order": dict(test=list(reversed(plan.test))),
             "representative": dict(representative={**plan.representative, "1": "kmhas:1:999"}),
             "groups": dict(groups={**plan.groups, "1": ["1", "2", "9"]}),
             "extra": dict(extra=[plan.representative["1"]])}
    with pytest.raises(ValueError):
        build_items(rows, replace(plan, **edits[change]), task, lists, label_rules)


def test_all_frozen_tasks_and_b1_template(label_rules):
    root = Path(__file__).resolve().parents[3] / "configs/tasks"
    lists = read_lists(root / "lists")
    tasks = [load_taskspec(p) for p in sorted(root.glob("*.yaml")) if p.stem != "b1"]
    assert len(tasks) == 7
    for task in tasks:
        specs = [q.to_dict() for q in task.questions] + ([task.per_item_questions] if task.per_item_questions else [])
        for spec in specs:
            assert spec["label"] in label_rules
            if spec.get("options") not in (None, "per_item"):
                assert spec["options"] in lists
    config = read_b1_config(root / "b1.yaml")
    q = BoundQuestion("q", "success", "noul", "instruction", None, {"true": "t", "false": "f"}, "x", None)
    result = build_b1_call(config, Rendered("state", 5), q, "q")
    assert result.messages[1]["content"] == "state\n\n질문: instruction\nA. [true] t\nB. [false] f\n답:"
