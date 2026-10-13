"""무엇: B1 문구·라벨 검증 · 입력: 합성 설정/기존 대응 fixture · 출력: B1Call 대조 · 계약 §2-5."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from jeveval.contract.b1_prompt import build_b1_call
from jeveval.types import B1Config, BoundQuestion, Rendered


ROOT = Path(__file__).parents[1] / "fixtures/b1"


def test_prompt_fixture_and_detached_configuration():
    fixture = json.loads((ROOT / "prompt.json").read_text())
    config = B1Config.from_dict(fixture["config"])
    rendered = Rendered.from_dict(fixture["rendered"])
    for case in fixture["cases"]:
        question = BoundQuestion.from_dict(case["question"])
        before = deepcopy((config, rendered, question))
        result = build_b1_call(config, rendered, question, case["call_qid"])
        assert result.call_qid == case["call_qid"]
        for key, value in case["expected"].items():
            assert getattr(result, key) == value
        assert (config, rendered, question) == before
        result.params["chat_template_kwargs"]["enable_thinking"] = True
        result.label_order.clear()
        assert config == before[0]
        assert "allowed_token_ids" not in result.params


def test_existing_label_mapping_option_lines():
    fixture = json.loads((ROOT / "label_mapping.json").read_text())
    question = BoundQuestion("pick", "success", fixture["question_type"], "골라요.",
                             fixture["criteria"], None, "synthetic", None)
    result = build_b1_call(B1Config("시스템", fixture["labels"], {}), Rendered("원문", 2), question, "q")
    assert result.label_map == fixture["expected"]["label_map"]
    user = result.messages[1]["content"]
    assert user == "원문\n\n질문: 골라요.\n" + "\n".join(fixture["expected"]["option_lines"]) + "\n답:"


def test_label_capacity_and_score():
    q = BoundQuestion("ready", "success", "noul", "준비?", None,
                      {"true": "예", "false": "아니오"}, "synthetic", None)
    config, rendered = B1Config("시스템", ["A"], {}), Rendered("원문", 2)
    with pytest.raises(ValueError):
        build_b1_call(config, rendered, q, "q")
    with pytest.raises(NotImplementedError):
        build_b1_call(config, rendered, replace(q, type="score"), "q")
