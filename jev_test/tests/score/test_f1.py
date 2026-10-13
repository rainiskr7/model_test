"""무엇: macro-F1 검증 · 입력: 기존 클래스 fixture · 출력: F1Result 대조 · 계약 §7-1."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeveval.score.f1 import macro_f1


def test_existing_fixture():
    path = Path(__file__).parents[1] / "fixtures/scoring/f1_classes.json"
    for case in json.loads(path.read_text())["cases"]:
        before = deepcopy(case)
        result = macro_f1(case["gold"], case["predicted"])
        assert result.to_dict() == case["expected"]
        assert case == before


@pytest.mark.parametrize("gold,predicted", [([], ["a"]), (["a"], [])])
def test_length_mismatch(gold, predicted):
    with pytest.raises(ValueError):
        macro_f1(gold, predicted)


def test_class_order_is_codepoint_order():
    assert macro_f1(["true", "NONE"], ["a", "false"]).classes == ["NONE", "a", "false", "true"]
