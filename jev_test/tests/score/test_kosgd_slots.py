"""무엇: 고정 칸·보정 경계 검증 · 입력: 기존 KoSGD fixture · 출력: 판정/Brier 대조 · 계약 §7-2."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeveval.score.calibration import calibrate
from jeveval.score.kosgd_slots import fixed_gold, judge_slots
from jeveval.types import ParsedAnswer


def test_existing_fixture_and_copy_prev():
    path = Path(__file__).parents[1] / "fixtures/scoring/kosgd_slots.json"
    fixture = json.loads(path.read_text())
    before = deepcopy(fixture)
    catalog = fixture["catalog_order"]
    for case in fixture["cases"]:
        result = judge_slots(case["predicted"], case["gold_intents"], catalog)
        assert fixed_gold(case["gold_intents"], catalog) == case["expected"]["fixed_gold"]
        for key, value in result.to_dict().items():
            assert value == case["expected"][key]
        if "copy_prev" in case:
            previous = judge_slots(case["copy_prev"], case["gold_intents"], catalog)
            assert previous.group_correct == case["expected"]["copy_prev_correct"]
    assert fixture == before


def test_fixed_brier_counterexample_per_slot_and_mean():
    path = Path(__file__).parents[1] / "fixtures/scoring/kosgd_slots.json"
    fixture = json.loads(path.read_text())
    case, catalog = fixture["counterexample"], fixture["catalog_order"]
    gold = fixed_gold(case["fixed_gold"], catalog)
    result = judge_slots(case["predicted"], gold, catalog)
    assert result.group_correct == case["expected"]["group_correct"]
    assert result.order_only == case["expected"]["order_only"]
    parsed = [ParsedAnswer("choice", answer, probs, probs[answer])
              for answer, probs in zip(case["predicted"], case["probabilities"])]
    slots = [calibrate([p], [g]).brier for p, g in zip(parsed, gold)]
    assert slots == pytest.approx(case["expected"]["fixed_slot_brier"])
    assert calibrate(parsed, gold).brier == pytest.approx(case["expected"]["fixed_mean_brier"])
    assert calibrate(parsed, case["predicted"]).brier == pytest.approx(
        case["expected"]["reassigned_mean_brier_forbidden"])


@pytest.mark.parametrize("gold,catalog", [(["a", "b", "c"], ["a", "b", "c"]),
    (["a", "a"], ["a"]), (["missing"], ["a"]), ([], ["a", "a"])])
def test_invalid_gold_or_catalog(gold, catalog):
    with pytest.raises(ValueError):
        fixed_gold(gold, catalog)
    with pytest.raises(ValueError):
        judge_slots(["NONE", "NONE"], gold, catalog)


@pytest.mark.parametrize("prediction", [[], ["a"], ["a", "b", "NONE"]])
def test_prediction_must_have_two_slots(prediction):
    with pytest.raises(ValueError):
        judge_slots(prediction, [], ["a", "b"])


def test_none_removed_before_count_and_catalog_checks():
    assert fixed_gold(["NONE", "a", "NONE", "NONE"], ["a"]) == ["a", "NONE"]
    assert fixed_gold(["NONE", "NONE"], []) == ["NONE", "NONE"]
    assert not judge_slots(["unknown", "NONE"], [], ["a"]).group_correct
