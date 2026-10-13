"""무엇: 요청 로컬 검증 · 입력: 합성 BoundQuestion/Request · 출력: 오류·순서 · 계약 §2."""

from copy import deepcopy
from dataclasses import replace

import pytest

from jeveval.contract.request import build_request, check_request
from jeveval.types import BoundQuestion, Rendered, Request


def question(qid="pick", kind="choice"):
    return BoundQuestion(qid, "success", kind, "골라요.",
                         {"z": "마지막", "NONE": "없음", "서비스/의도": "의도"},
                         {"true": "예", "false": "아니오"}, "synthetic", None)


def request():
    return build_request("model", Rendered("원문", 2), [question()])


def test_order_detachment_and_no_metadata_on_wire():
    questions = [question("z"), question("a", "noul")]
    before = deepcopy(questions)
    result = build_request("model", Rendered("원문", 2), questions)
    assert list(result.questions) == ["z", "a"]
    assert list(result.questions["z"]["criteria"]) == ["z", "NONE", "서비스/의도"]
    assert set(result.questions["z"]) == {"type", "instructions", "criteria"}
    assert check_request(result, "model") == []
    result.questions["z"]["criteria"]["z"] = "바뀜"
    assert questions == before


def test_duplicate_question_rejected_before_dict_conversion():
    with pytest.raises(ValueError, match="duplicate"):
        build_request("model", Rendered("원문", 2), [question(), question()])


@pytest.mark.parametrize("qid", ["A", "한글", "a__b", "a_", "1_a", "a_１", ""])
def test_question_id_only_is_snake_case(qid):
    result = build_request("model", Rendered("원문", 2), [question(qid)])
    assert any("snake_case" in e for e in check_request(result, "model"))


@pytest.mark.parametrize("criteria", [None, [], {}, {"a": ""}, {"": "a"}, {1: "a"},
    {"NONE": "없음", "none": "충돌"}, {"ß": "a", "ss": "b"}])
def test_bad_choice_criteria(criteria):
    result = request()
    result.questions["pick"]["criteria"] = criteria
    assert check_request(result, "model")


@pytest.mark.parametrize("n,valid", [(1, True), (255, True), (256, False)])
def test_choice_count(n, valid):
    result = request()
    result.questions["pick"]["criteria"] = {str(i): "설명" for i in range(n)}
    assert (check_request(result, "model") == []) is valid


@pytest.mark.parametrize("criteria", [{"true": "예"}, {True: "예", False: "아니오"},
    {"true": "예", "false": "아니오", "extra": "값"}])
def test_noul_requires_exact_string_keys(criteria):
    result = build_request("model", Rendered("원문", 2), [question(kind="noul")])
    result.questions["pick"]["criteria"] = criteria
    assert check_request(result, "model")


@pytest.mark.parametrize("field,value", [("model", ""), ("state", []), ("state", " \n"),
    ("questions", []), ("questions", {}), ("questions", {"q": None})])
def test_bad_fields(field, value):
    assert check_request(replace(request(), **{field: value}), "model")


def test_independent_errors_accumulate_without_mutation():
    result = Request("wrong", "", {"Bad": {"type": "other", "instructions": False, "criteria": None}})
    before = deepcopy(result)
    assert len(check_request(result, "model")) >= 5
    assert result == before


def test_score_out_of_scope():
    with pytest.raises(NotImplementedError):
        build_request("model", Rendered("원문", 2), [question(kind="score")])
    with pytest.raises(NotImplementedError):
        check_request(Request("model", "원문", {"q": {"type": "score"}}), "model")
