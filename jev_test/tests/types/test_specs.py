"""무엇: 설정·식별·분할 JSON 왕복 · 입력: 합성 객체 · 출력: 검증 · 계약 §1·§6·§8-1."""

from dataclasses import FrozenInstanceError
import json

import pytest

from jeveval.types import Item, QuestionSpec, SplitPlan, TaskSpec


@pytest.fixture
def task():
    return TaskSpec(
        set="synthetic", variant="full", state={"kind": "plain_text"},
        questions=[QuestionSpec("ready_1", "success", "noul", "준비됐나요?", "ready",
                                criteria={"true": "준비됐다.", "false": "아직이다."})],
        per_item_questions=None, group_key="source",
    )


@pytest.mark.parametrize("record", [
    Item("synthetic", "g1", "i1"), Item("functionchat", 11, 12),
    QuestionSpec("pick_one", "success", "choice", "하나를 골라요.", "pick", options="per_item"),
    SplitPlan("synthetic", 20261012, "all", {}, {"g1": ["i1", "i2"]},
              {"g1": "synthetic:g1:i1"}, [], ["g1"], []),
    SplitPlan("functionchat", 20261012, "all", {}, {"11": [11, 12]},
              {"11": "functionchat:11:12"}, [], ["11"], []),
])
def test_roundtrip(record):
    assert type(record).from_dict(json.loads(json.dumps(record.to_dict()))) == record
    with pytest.raises(FrozenInstanceError):
        record.set = "changed"


def test_task_nested_roundtrip(task):
    result = TaskSpec.from_dict(json.loads(json.dumps(task.to_dict(), ensure_ascii=False)))
    assert result == task
    assert isinstance(result.questions[0], QuestionSpec)
    assert result.questions is not task.questions
    assert result.questions[0].criteria is not task.questions[0].criteria


def test_serialization_does_not_alias(task):
    data = task.to_dict()
    restored = TaskSpec.from_dict(data)
    data["questions"][0]["criteria"]["true"] = "바뀐 문장"
    assert restored == task
    data["state"]["kind"] = "changed"
    assert restored.state == {"kind": "plain_text"}


def test_unknown_or_missing_fields_fail():
    with pytest.raises(ValueError, match="unknown fields"):
        Item.from_dict({"set": "s", "group_id": "g", "item_id": "i", "guess": 1})
    with pytest.raises(TypeError):
        Item.from_dict({"set": "s"})


@pytest.mark.parametrize("data", [[], None, {"set": "s", "group_id": True, "item_id": "i"}])
def test_wrong_types_fail(data):
    with pytest.raises(TypeError):
        Item.from_dict(data)
