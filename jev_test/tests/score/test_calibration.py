"""무엇: 보정 지표 검증 · 입력: 기존 보정 fixture·서로 다른 선택지 · 출력: CalibResult · 계약 §7-1."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeveval.score.answers import parse_systemone
from jeveval.score.calibration import calibrate
from jeveval.types import ParsedAnswer


def test_existing_fixture():
    path = Path(__file__).parents[1] / "fixtures/scoring/calibration.json"
    for kind, case in json.loads(path.read_text())["questions"].items():
        kind = case.get("type", kind)
        rows = case["observations"]
        parsed = [ParsedAnswer(kind, r["answer"], r["probs"], r["confidence"]) for r in rows]
        gold = [r["gold"] for r in rows]
        before = deepcopy((parsed, gold))
        result, expected = calibrate(parsed, gold), case["expected"]
        for key in ("ece", "brier", "log_loss"):
            value = expected[key]
            assert getattr(result, key) == (pytest.approx(value) if value is not None else None)
        assert len(result.bins) == 15 and sum(b["n"] for b in result.bins) == len(rows)
        for actual, wanted in zip(result.bins, expected["bins"]):
            assert actual == pytest.approx(wanted)
        assert (parsed, gold) == before


@pytest.mark.parametrize("parsed,gold", [([], ["a"]), ([ParsedAnswer("choice", "a", {"a": 1}, 1)], [])])
def test_length_mismatch(parsed, gold):
    with pytest.raises(ValueError):
        calibrate(parsed, gold)


def test_missing_gold_key():
    with pytest.raises(ValueError):
        calibrate([ParsedAnswer("choice", "a", {"a": 1}, 1)], ["missing"])


def test_different_observation_keys_are_allowed():
    parsed = [ParsedAnswer("choice", "tool_a", {"tool_a": 1, "NONE": 0}, 1),
              ParsedAnswer("choice", "tool_z", {"tool_z": 1, "NONE": 0}, 1)]
    result = calibrate(parsed, ["tool_a", "tool_z"])
    assert result.ece == result.brier == result.log_loss == 0


def test_parser_to_calibration_uses_selected_probability_independent_of_confidence():
    answer = dict(type="choice", choice="b", probabilities={"a": .8, "b": .2}, confidence=.05)
    parsed = parse_systemone(answer, "choice").parsed
    result = calibrate([parsed], ["b"])
    assert result.ece == pytest.approx(.8)
    assert result.bins[3]["n"] == 1
    assert result.brier == pytest.approx(1.28)
    for confidence in (0, .3, 1):
        answer["confidence"] = confidence
        assert calibrate([parse_systemone(answer, "choice").parsed], ["b"]) == result


def test_all_bin_boundaries_are_left_closed():
    parsed = [ParsedAnswer("choice", "a", {"a": i / 15, "b": 1 - i / 15}, i / 15)
              for i in range(16)]
    result = calibrate(parsed, ["a"] * 16)
    assert [b["n"] for b in result.bins] == [1] * 14 + [2]
