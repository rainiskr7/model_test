"""무엇: 질문 확장 검사 · 입력: 기존 KorFin fixture·합성 task · 출력: 질문·오류 대조 · 계약 §1-1·§6-2."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from jeveval.contract.taskspec import validate_taskspec
from jeveval.data.expand import expand_questions
from jeveval.types import QuestionSpec, TaskSpec


@pytest.fixture
def fixture():
    return json.loads((Path(__file__).parents[1] / "fixtures/expand/korfin.json").read_text())


def test_existing_fixture_actual_expansion(fixture):
    task = validate_taskspec(fixture["task"])
    bindings = [{"k": i, "ASPECT": r["ASPECT"]} for i, r in enumerate(fixture["rows"], 1)]
    by_aspect = {r["ASPECT"]: r["gold"] for r in fixture["rows"]}
    lists = {"sentiment": fixture["options"]}
    before = deepcopy((task, lists, bindings))
    bound = expand_questions(task, lists, None, bindings, lambda label, b, o: by_aspect[b["ASPECT"]])
    assert [q.to_dict() for q in bound] == fixture["expected"]["questions"]
    bound[0].options.clear()
    assert bound[1].options == fixture["options"]
    assert (task, lists, bindings) == before


def test_unbounded_schema_collision_fixture(fixture):
    for qid in fixture["collision_ids"] + fixture["noncollision_ids"]:
        task = deepcopy(fixture["task"])
        task["questions"] = [dict(id=qid, role="diagnostic", type="choice", instructions="x",
                                  options="sentiment", label="static")]
        assert isinstance(validate_taskspec(task), list) == (qid in fixture["collision_ids"])


def test_runtime_collisions_static_first_and_ascii(fixture):
    task = validate_taskspec(fixture["task"])
    q = QuestionSpec("first", "diagnostic", "noul", "static", "static", criteria={"true": "t", "false": "f"})
    task = replace(task, questions=[q])
    kwargs = dict(lists={"sentiment": fixture["options"]}, item_options=None,
                  bindings=[{"k": 1, "ASPECT": "a"}],
                  gold_of=lambda label, b, o: "false" if label == "static" else "pos")
    result = expand_questions(task, **kwargs)
    assert [r.id for r in result] == ["first", "aspect_1"]
    for qid in ["aspect_1", "BAD", "한글"]:
        with pytest.raises(ValueError):
            expand_questions(replace(task, questions=[replace(q, id=qid)]), **kwargs)
    with pytest.raises(ValueError, match="duplicate"):
        expand_questions(task, **{**kwargs, "bindings": kwargs["bindings"] * 2})


def test_template_values_not_recursively_replaced(fixture):
    task = validate_taskspec(fixture["task"])
    task = replace(task, per_item_questions={**task.per_item_questions,
                                           "instructions_template": "{ASPECT}|{k}"})
    bound = expand_questions(task, {"sentiment": fixture["options"]}, None,
                             [{"ASPECT": "{k}{x}", "k": 1}], lambda *args: None)
    assert bound[0].instructions == "{k}{x}|1" and bound[0].gold is None
    with pytest.raises(ValueError, match="binding"):
        expand_questions(task, {"sentiment": fixture["options"]}, None,
                         [{"k": 1}], lambda *args: None)


@pytest.mark.parametrize("answer", ["outside", True, 1])
def test_gold_outside_choice_and_noul(answer):
    for kind in ("choice", "noul"):
        q = QuestionSpec("q", "success", kind, "x", "x", options="per_item",
                         criteria={"true": "t", "false": "f"})
        task = TaskSpec("s", "default", {}, [q], None, "text")
        with pytest.raises(ValueError, match="gold"):
            expand_questions(task, {}, {"yes": "y"}, [], lambda *args: answer)


def test_missing_per_item_and_static_binding():
    q = QuestionSpec("q", "success", "choice", "x", "x", options="per_item")
    task = TaskSpec("s", "default", {}, [q], None, "text")
    with pytest.raises(ValueError, match="options"):
        expand_questions(task, {}, None, [], lambda *args: None)
    seen = []
    result = expand_questions(task, {}, {"yes": "y"}, [], lambda l, b, o: seen.append((b, o)))
    assert seen == [({}, {"yes": "y"})] and result[0].gold is None
