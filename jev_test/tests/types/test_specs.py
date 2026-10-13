"""무엇: 설정·식별·분할 JSON 왕복 · 입력: 합성 객체 · 출력: 검증 · 계약 §1·§6·§8-1."""

from dataclasses import FrozenInstanceError
import json

import pytest

from jeveval.types import BoundQuestion, Item, QuestionSpec, SplitPlan, TaskSpec
from samples import item


@pytest.fixture
def task():
    return TaskSpec(
        set="synthetic", variant="full", state={"kind": "plain_text"},
        questions=[QuestionSpec(id="ready_1", role="success", type="noul", instructions="준비됐나요?", label="ready",
                                criteria={"true": "준비됐다.", "false": "아직이다."})],
        per_item_questions=None, group_key="source",
    )


@pytest.mark.parametrize("record", [
    item(),
    QuestionSpec(id="pick_one", role="success", type="choice", instructions="골라요.", label="pick", options="per_item"),
    SplitPlan(set="synthetic", seed=20261012, pool_rule="all", allocation={}, groups={"g1":["i1","i2"]},
              representative={"g1":"synthetic:g1:i1"}, dev=[], test=["g1"], diagnostic_demotions=[],
              extra=["synthetic:g1:i2"], notes={"label_conflict_groups":0}),
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


def test_item_questions_restored_and_detached():
    original = item()
    source = original.to_dict()
    restored = Item.from_dict(source)
    assert isinstance(restored.questions[0], BoundQuestion)
    source["questions"][0]["criteria"]["true"] = "변경"
    source["meta"]["flags"].append("label_conflict_group")
    assert restored == original


def test_numeric_item_identifiers_rejected():
    for key in ("group_id", "item_id"):
        source = item().to_dict()
        source[key] = 11
        with pytest.raises(TypeError):
            Item.from_dict(source)
