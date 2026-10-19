"""공통 항목 선택, 묶음 검증 및 원문 없는 요약."""

from dataclasses import replace

import pytest

from jeveval.data.items.common import _selected, assemble, conflict_flags, fields, summarize
from jeveval.types import SourceRow
from tests.types.samples import bound, item


@pytest.mark.parametrize("rule,item_id,expected", [("SRC", "ignored", ["a", "b"]),
    ("dialogue_id", "2", ["b"]), ("text", "a", ["a"])])
def test_selected_source_rules(rule, item_id, expected):
    rows = [SourceRow("s", "a", {"turn_index": 0}), SourceRow("s", "b", {"turn_index": 2})]
    assert [r.row_id for r in _selected(rows, item_id, rule)] == expected


@pytest.mark.parametrize("duplicate", [False, True])
def test_selected_requires_exactly_one_row(duplicate):
    rows = [SourceRow("s", "a", {})] * (2 if duplicate else 0)
    with pytest.raises(ValueError, match="^logical_id does not identify one source row$"):
        _selected(rows, "a", "text")


def test_plan_groups_mismatch_precedes_item_callback(settings, plan_for):
    task, _ = settings("kmhas")
    rows = [SourceRow("kmhas", "0", {"text": "first"}), SourceRow("kmhas", "1", {"text": "second"})]
    plan = plan_for(rows, task)
    changed = [rows[0], replace(rows[1], fields={"text": "first"})]
    def forbidden(*args):
        pytest.fail("invalid groups reached item construction")
    with pytest.raises(ValueError, match="^plan.groups mismatch$"):
        assemble(changed, plan, task, forbidden)


@pytest.mark.parametrize("labels,expected", [([[1, 2], [2, 1, 1]], []),
    ([[1], [2]], ["label_conflict_group"]), ([], [])])
def test_conflict_flags_ignore_order_and_duplicates(labels, expected):
    rows = [SourceRow("s", str(i), {"label": value}) for i, value in enumerate(labels)]
    assert conflict_flags(rows, "label") == expected


@pytest.mark.parametrize("field,value", [("label", [True]), ("label", ["1"]),
                                        ("labels_majority", [1]), ("label", None)])
def test_conflict_flags_reject_invalid_label_types(field, value):
    with pytest.raises(ValueError, match=f"^invalid label field: {field}$"):
        conflict_flags([SourceRow("s", "0", {field: value})], field)


def test_summary_shape_counts_and_field_detachment():
    question = bound()
    content = fields("PRIVATE", [question], stratum="small", flags=["warning:a", "warning:b"], baseline={})
    value = replace(item(), state_fields=content.state_fields, questions=content.questions,
                    meta=content.meta, baseline=content.baseline)
    result = summarize({"dev": [value], "test": []})
    assert result == {"dev": dict(n=1, questions={"ready": dict(role="success", type="noul",
        n_options=2, gold={"MISSING": 0, "true": 1, "false": 0})}, flags={"warning": 1},
        stratum={"small": 1}, baseline=1),
        "test": dict(n=0, questions={}, flags={}, stratum=None, baseline=0)}
    assert "PRIVATE" not in str(result) and content.questions[0] is not question
    other = replace(value, questions=[replace(question, role="diagnostic")])
    with pytest.raises(ValueError, match="^inconsistent question summary shape$"):
        summarize({"dev": [value, other]})
