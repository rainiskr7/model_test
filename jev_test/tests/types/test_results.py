"""무엇: 결과 타입 JSON 왕복 · 입력: 합성 결과 · 출력: 검증 · 계약 §3·§5-3·§7-4."""

from dataclasses import FrozenInstanceError
import json

import pytest

from jeveval.types import LengthInfo, ParsedAnswer, RiskCell, ScoreTable, Threshold


@pytest.mark.parametrize("record", [
    ParsedAnswer("noul", noul=.5),
    ParsedAnswer("choice", choice="a", confidence=.7, probabilities={"a": .7, "b": .3}),
    LengthInfo(100, 80), Threshold(.9), Threshold(None), ScoreTable(),
])
def test_result_roundtrip(record):
    assert type(record).from_dict(json.loads(json.dumps(record.to_dict()))) == record
    with pytest.raises(FrozenInstanceError):
        record.guessed_field = 1


def test_risk_cells_roundtrip():
    record = RiskCell("NO_THRESHOLD", True, None, {"groups": 1, "n": 0, "k": 0},
                      {"groups": 4, "n": None, "k": None, "U": None,
                       "coverage": 0, "b_flip": None},
                      {"ok": 1, "rejected": 1, "truncated": 1, "error": 1}, {}, {})
    data = json.loads(json.dumps(record.to_dict()))
    assert RiskCell.from_dict(data) == record


def test_unspecified_score_fields_are_not_silently_accepted():
    with pytest.raises(ValueError, match="unknown fields"):
        ScoreTable.from_dict({"accuracy": .5})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_non_json_numbers_rejected(value):
    with pytest.raises(ValueError):
        Threshold(value).to_dict()
    with pytest.raises(ValueError):
        Threshold.from_dict({"t_star": value})
