"""무엇: task 스키마 경계 검사 · 입력: 합성 dict · 출력: 통과/오류 · 계약 §1-1."""

from copy import deepcopy

import pytest

from jeveval.contract.taskspec import validate_taskspec
from jeveval.types import TaskSpec


@pytest.fixture
def document():
    return {
        "set": "synthetic", "variant": "full", "state": {"kind": "plain_text"},
        "questions": [{"id": "ready_1", "role": "success", "type": "noul",
                       "instructions": "준비됐나요?", "label": "ready",
                       "criteria": {"true": "준비됐다.", "false": "아직이다."}}],
        "per_item_questions": None, "group_key": "source",
    }


def test_valid_pure_and_detached(document):
    before = deepcopy(document)
    result = validate_taskspec(document)
    assert isinstance(result, TaskSpec)
    assert document == before
    document["questions"][0]["criteria"]["true"] = "변경"
    assert result.questions[0].criteria["true"] == "준비됐다."


def test_choice_and_json_key_order(document):
    document["state"] = {"kind": "json_string", "keys": ["z", "a"]}
    document["questions"].append({"id": "pick_one", "role": "diagnostic", "type": "choice",
                                  "instructions": "골라요.", "options": "per_item", "label": "pick"})
    result = validate_taskspec(document)
    assert isinstance(result, TaskSpec)
    assert result.state["keys"] == ["z", "a"]
    assert [q.id for q in result.questions] == ["ready_1", "pick_one"]


@pytest.mark.parametrize("key", ["set", "variant", "state", "questions", "per_item_questions", "group_key"])
def test_missing_top_key(document, key):
    del document[key]
    assert any(f"task.{key}: required" in error for error in validate_taskspec(document))


@pytest.mark.parametrize("key", ["id", "role", "type", "instructions", "label"])
def test_missing_question_key(document, key):
    del document["questions"][0][key]
    assert any(f".{key}: required" in error for error in validate_taskspec(document))


@pytest.mark.parametrize("qid", ["한글", "A_b", "a__b", "_a", "a_", "1_a", "a-b", "a b", "a_１", ""])
def test_bad_question_id(document, qid):
    document["questions"][0]["id"] = qid
    assert any("ASCII snake_case" in e for e in validate_taskspec(document))


@pytest.mark.parametrize("field,value,fragment", [
    ("role", "other", ".role:"), ("type", "score", "score is out of scope"),
    ("type", "unknown", ".type:"), ("instructions", " \n", ".instructions:"),
    ("instructions", False, ".instructions:"), ("criteria", {}, ".criteria:"),
    ("criteria", {"true": "예", "false": ""}, ".criteria:"),
    ("criteria", {"true": True, "false": "아니오"}, ".criteria:"),
    ("criteria", {True: "예", False: "아니오"}, ".criteria:"),
])
def test_question_errors(document, field, value, fragment):
    document["questions"][0][field] = value
    assert any(fragment in e for e in validate_taskspec(document))


@pytest.mark.parametrize("state", [None, [], {}, {"kind": "other"}, {"kind": "json_string"},
                                    {"kind": "json_string", "keys": []},
                                    {"kind": "json_string", "keys": [""]}])
def test_invalid_state(document, state):
    document["state"] = state
    assert any("task.state" in e for e in validate_taskspec(document))


@pytest.mark.parametrize("options", [None, "", [], False])
def test_choice_needs_options(document, options):
    document["questions"][0].update(type="choice", options=options)
    assert any(".options:" in e for e in validate_taskspec(document))


def test_duplicate_id(document):
    document["questions"].append(deepcopy(document["questions"][0]))
    assert any("duplicate" in e for e in validate_taskspec(document))


@pytest.mark.parametrize("questions", [[], None, {}, [None]])
def test_malformed_or_empty_questions(document, questions):
    document["questions"] = questions
    assert isinstance(validate_taskspec(document), list)


def test_no_success(document):
    document["questions"][0]["role"] = "diagnostic"
    assert any("at least one success" in e for e in validate_taskspec(document))


@pytest.mark.parametrize("data", [None, [], "text", 1])
def test_bad_document_root(data):
    assert validate_taskspec(data) == ["task: expected object"]


def test_errors_accumulate_without_mutation(document):
    document["questions"][0].update(role="other", type="score", instructions="")
    before = deepcopy(document)
    result = validate_taskspec(document)
    assert len(result) >= 4
    assert document == before
