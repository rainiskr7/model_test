"""무엇: FunctionChat 항목 검사 · 입력: 합성 행 · 출력: 정규화·선택지·extra · 계약 §6-2."""

from copy import deepcopy

import pytest

from jeveval.data.items.functionchat import S, build_items
from jeveval.types import SourceRow


def _row(i, content, action="slot"):
    tools = [{"function": {"name": name, "description": name + " desc"}} for name in ["z", "a"]]
    truth = {"tool_calls": [{"function": {"name": "a"}}]} if action == "call" else {}
    return SourceRow("fc_call_decision", str(i), dict(serial_num=i, input_tools=tools,
        input_messages=[dict(role="system", content=content), dict(role="user", content="u")],
        type_of_output=action, ground_truth=truth))


def test_normalization_options_order_extra_and_detachment(settings, plan_for, label_rules):
    task, lists = settings("fc_call_decision")
    rows = [_row(2, S + " " + S), _row(1, S, "call"), _row(3, "no sentence")]
    plan = plan_for(rows, task, extra=["fc_call_decision:1:2", "fc_call_decision:1:3"])
    before = deepcopy((rows, lists, task, plan))
    result = build_items(rows, plan, task, lists, label_rules)
    assert [i.item_id for i in result["extra"]] == ["2", "3"]
    assert [i.group_id for i in result["extra"]] == ["1", "1"]
    assert result["test"] == []
    item = result["extra"][0]
    assert item.state_fields["input_messages"][0]["content"] == S
    assert list(item.questions[1].options) == ["z", "a", "NONE"]
    assert [q.gold for q in result["dev"][0].questions] == ["call", "a"]
    assert [q.gold for q in item.questions] == ["slot", "NONE"]
    assert item.meta == dict(service=None, stratum=None, flags=[]) and item.baseline is None
    item.state_fields["input_tools"][0]["function"]["name"] = "changed"
    item.questions[1].options.clear()
    assert (rows, lists, task, plan) == before


@pytest.mark.parametrize("content", [" ".join([S] * 3), S + "\n" + S, S + " x " + S])
def test_remaining_repetitions_stop(settings, plan_for, content, label_rules):
    task, lists = settings("fc_call_decision")
    rows = [_row(1, content)]
    with pytest.raises(ValueError, match="remains"):
        build_items(rows, plan_for(rows, task), task, lists, label_rules)


@pytest.mark.parametrize("name", ["z", "NONE"])
def test_bad_tool_names_stop(settings, plan_for, name, label_rules):
    task, lists = settings("fc_call_decision")
    rows = [_row(1, S)]
    rows[0].fields["input_tools"][1]["function"]["name"] = name
    with pytest.raises(ValueError, match="tool name"):
        build_items(rows, plan_for(rows, task), task, lists, label_rules)
