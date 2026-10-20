"""9-1a extracted aggregation; literal statistics underlying the 9-0 report."""

from copy import deepcopy
import json

import pytest

from shared.functionchat.judge import analyze_pilot as analyze


def test_analyze_records_counts_errors_flips_disagreement_and_scores():
    records = [
        {"type_of_output": "call", "judges": {
            "weak": [{"verdict": "pass"}, {"verdict": "pass"}, {"verdict": "fail"}],
            "strong": [{"verdict": "fail"}],
        }},
        {"type_of_output": "call", "judges": {
            "weak": [{"verdict": "pass"}, {"verdict": "fail"}, {"error": "timeout"}],
            "strong": [{"verdict": None}],
        }},
    ]
    original = deepcopy(records)
    assert analyze._analyze_records(records, "weak", "strong") == (
        {"weak:transport": 1, "strong:parse": 1},
        {"call": [2, 2]}, {"call": [1, 1]},
        {"weak": {"call:pass": 1}, "strong": {"call:fail": 1}},
    )
    assert records == original


def test_analyze_records_empty_calls_do_not_share_accumulators():
    first = analyze._analyze_records([], "weak", None)
    second = analyze._analyze_records([], "weak", None)
    assert first == second == ({}, {}, {}, {})
    assert all(a is not b for a, b in zip(first, second))


def test_main_reaches_patched_majority_before_printing(tmp_path, monkeypatch, capsys):
    path = tmp_path / "pilot.json"
    path.write_text(json.dumps({"models": ["weak"], "repeats": 1, "records": [
        {"type_of_output": "slot", "judges": {"weak": [{"verdict": "pass"}]}},
    ]}), encoding="utf-8")
    calls = []
    failure = ValueError("patched majority")

    def majority(verdicts):
        calls.append(verdicts)
        raise failure

    monkeypatch.setattr(analyze, "majority", majority)
    with pytest.raises(ValueError) as caught:
        analyze.main(["--pilot", str(path)])
    assert caught.value is failure
    assert calls == [["pass"]]
    assert capsys.readouterr() == ("", "")
