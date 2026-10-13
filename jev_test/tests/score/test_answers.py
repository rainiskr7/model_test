"""무엇: systemone·B1 파싱 검증 · 입력: 기존 fixture·토큰 경계 · 출력: AnswerParse 대조 · 계약 §3-2."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeveval.contract.b1_prompt import build_b1_call
from jeveval.contract.response import validate_response
from jeveval.score.answers import parse_b1, parse_systemone
from jeveval.types import B1Config, BoundQuestion, Rendered, Request


ROOT = Path(__file__).parents[1] / "fixtures"


def read(name):
    return json.loads((ROOT / name).read_text())


def assert_parsed(actual, expected):
    assert actual.type == expected["type"] and actual.answer == expected["answer"]
    assert actual.probs == pytest.approx(expected["probs"])
    assert actual.confidence == pytest.approx(expected["confidence"])


def test_systemone_fixture_through_validator():
    for case in read("answers/systemone.json")["cases"]:
        raw = case["raw"]
        before = deepcopy(raw)
        req = Request("m", "s", {"q": {"type": raw["type"],
                      "criteria": {key: key for key in raw.get("probabilities", {})}}})
        validated = validate_response(json.dumps({"answers": {"q": raw}}), req)
        assert validated.reason is None
        result = parse_systemone(validated.answers["q"], raw["type"])
        assert result.parsed.to_dict() == case["expected"]["parsed"]
        assert result.warnings == case["expected"]["warnings"]
        assert result.reason is None and result.label_probs is None
        result.parsed.probs.clear()
        assert raw == before and validated.answers["q"] == before


def test_b1_renormalization_fixture():
    for case in read("b1/renormalization.json")["cases"]:
        before = deepcopy(case)
        result = parse_b1(case["top_logprobs"], case["label_order"], case["label_map"], case["type"])
        expected = case["expected"]
        assert ("ok" if result.reason is None else "error") == expected["status"]
        assert result.label_probs == pytest.approx(expected["label_probabilities"])
        assert_parsed(result.parsed, expected["parsed"])
        assert result.warnings == (["b1_extra_token"] if case["name"] == "renormalize" else [])
        assert case == before


def test_b1_missing_fixture():
    fixture = read("b1/missing_label.json")
    for case in fixture["cases"]:
        rows = case.get("top_logprobs") or json.loads(case["top_logprobs_raw"])
        result = parse_b1(rows, list(fixture["label_map"]), fixture["label_map"], "noul")
        assert ("error" if result.reason else "ok") == fixture["expected"]["status"]
        assert result.reason == fixture["expected"]["reason"]
        assert result.parsed is None and result.label_probs is None


def test_strip_duplicates_maximum_extra_token_and_stable_softmax():
    rows = [{"token": " Z ", "logprob": 0}, {"token": " A", "logprob": -1001},
            {"token": "B\n", "logprob": -1000}, {"token": "A ", "logprob": -999},
            {"token": "A", "logprob": -1002}, {"token": "X", "logprob": 1}]
    result = parse_b1(rows, ["A", "B"], {"A": "a", "B": "b"}, "choice")
    assert result.warnings == ["b1_extra_token", "b1_duplicate_label"]
    assert result.parsed.answer == "a"
    assert result.parsed.confidence == pytest.approx(.7310585786300049)
    assert sum(result.label_probs.values()) == pytest.approx(1)


def test_choice_tie_uses_label_order_not_token_order():
    rows = [{"token": "A", "logprob": -1}, {"token": "B", "logprob": -1}]
    result = parse_b1(rows, ["B", "A"], {"B": "z", "A": "a"}, "choice")
    assert result.parsed.answer == "z" and result.parsed.confidence == .5


def test_prompt_to_parser_boundary():
    question = BoundQuestion("pick", "success", "choice", "골라요.",
                             {"z": "마지막", "NONE": "없음"}, None, "synthetic", None)
    config = B1Config("시스템", "{state}\n\n질문: {instructions}\n{options}\n답:", ["X", "Y"], {})
    call = build_b1_call(config, Rendered("원문", 2), question, "q")
    result = parse_b1([{"token": "Y", "logprob": -.1}, {"token": " X", "logprob": -2}],
                      call.label_order, call.label_map, question.type)
    assert result.parsed.answer == "z"


def test_missing_preserves_warnings():
    result = parse_b1([{"token": "X", "logprob": 0}], ["A", "B"], {"A": "true", "B": "false"}, "noul")
    assert result.reason == "b1_missing_label" and result.warnings == ["b1_extra_token"]


def test_score_out_of_scope():
    with pytest.raises(NotImplementedError):
        parse_systemone({}, "score")
    with pytest.raises(NotImplementedError):
        parse_b1([], [], {}, "score")
