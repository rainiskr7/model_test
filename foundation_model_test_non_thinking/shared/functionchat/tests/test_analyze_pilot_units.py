"""9-0 stdout and exceptions captured from synthetic pilot inputs; no variable fields."""

import json

import pytest

from shared.functionchat.judge import analyze_pilot


MIXED = {
    "models": ["weak", "strong"], "repeats": 3,
    "records": [
        {"type_of_output": "dialog", "judges": {
            "weak": [{"verdict": "pass"}, {"verdict": "fail"}, {"verdict": "pass"}],
            "strong": [{"verdict": "fail"}],
        }},
        {"type_of_output": "call", "judges": {
            "weak": [{"verdict": "fail"}, {"verdict": "fail"}, {"verdict": "pass"}],
            "strong": [{"verdict": "fail"}],
        }},
        {"type_of_output": "call", "judges": {
            "weak": [{"verdict": "pass"}, {"verdict": "fail"},
                     {"error": "timeout", "verdict": None}],
            "strong": [{"verdict": "pass"}],
        }},
        {"type_of_output": "dialog", "judges": {
            "weak": [{"verdict": None}], "strong": [{"error": "down", "verdict": None}],
        }},
    ],
}
SINGLE = {
    "models": ["weak"], "repeats": 2,
    "records": [{"type_of_output": "call", "judges": {
        "weak": [{"verdict": "pass"}, {"verdict": "pass"}],
    }}],
}
MIXED_STDOUT = """  판정기: 약=weak  강=strong
  표본 4건, 약한 판정기 반복 3회

  1) 파싱/전송 실패
     {'weak:transport': 1, 'weak:parse': 1, 'strong:transport': 1}

  2) 약한 판정기 반복 뒤집힘 (일관성)
     call         2/2 = 100.0%
     dialog       1/2 = 50.0%
     전체           3/4 = 75.0%

  3) 약 vs 강 불일치 (타당도 대리 지표)
     call         0/1 = 0.0%
     dialog       1/1 = 100.0%
     전체           1/2 = 50.0%  (일치 50.0%)

  4) 판정기별 통과율
     weak                     call 0/1  dialog 1/1
     strong                   call 1/2  dialog 0/1
"""
SINGLE_STDOUT = """  판정기: 약=weak  강=None
  표본 1건, 약한 판정기 반복 2회

  1) 파싱/전송 실패
     0건 — 구조화 출력이 안정적이다

  2) 약한 판정기 반복 뒤집힘 (일관성)
     call         0/1 = 0.0%
     전체           0/1 = 0.0%

  3) 약 vs 강 불일치 (타당도 대리 지표)
  4) 판정기별 통과율
     weak                     call 1/1
"""
EMPTY_STDOUT = """  판정기: 약=weak  강=strong
  표본 0건, 약한 판정기 반복 3회

  1) 파싱/전송 실패
     0건 — 구조화 출력이 안정적이다

  2) 약한 판정기 반복 뒤집힘 (일관성)
"""


def _pilot(tmp_path, value):
    path = tmp_path / "pilot.json"
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return ["--pilot", str(path)]


@pytest.mark.parametrize("payload,expected", [(MIXED, MIXED_STDOUT), (SINGLE, SINGLE_STDOUT)])
def test_main_stdout_and_rc(tmp_path, capsys, payload, expected):
    assert analyze_pilot.main(_pilot(tmp_path, payload)) == 0
    assert capsys.readouterr() == (expected, "")


def test_empty_models_raises_before_any_output(tmp_path, capsys):
    with pytest.raises(IndexError) as caught:
        analyze_pilot.main(_pilot(tmp_path, {"models": [], "repeats": 3, "records": []}))
    assert str(caught.value) == "list index out of range"
    assert capsys.readouterr() == ("", "")


def test_empty_records_preserves_partial_stdout_before_division_error(tmp_path, capsys):
    with pytest.raises(ZeroDivisionError) as caught:
        analyze_pilot.main(_pilot(tmp_path, {
            "models": ["weak", "strong"], "repeats": 3, "records": [],
        }))
    assert str(caught.value) == "division by zero"
    assert capsys.readouterr() == (EMPTY_STDOUT, "")


@pytest.mark.parametrize("verdicts,expected", [
    ([], None), ([None, None], None), (["pass", "fail"], None),
    (["fail", "pass"], None), (["pass", None, "pass", "fail"], "pass"),
    (["fail", "fail", "pass"], "fail"),
])
def test_majority_requires_more_than_half_of_non_null_votes(verdicts, expected):
    assert analyze_pilot.majority(verdicts) == expected
