"""무엇: 비용 fixture·기록 경계 · 입력: 기존 시도 fixture·합성 final · 출력: Cost 대조 · 계약 §7-6."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from jeveval.io.records import read_attempts, read_finals, record_line
from jeveval.io.run_files import json_bytes
from jeveval.score.cost import cost, cost_by_stage
from jeveval.types import AttemptRecord, CallRecord, Cost, FinalRecord, ScoreTable


def attempt(*, call_id="call", logical_id="logical", raw="{}", terminal=True, number=1,
            session="one", status=200, start="2026-10-13T00:00:00.000Z", end="2026-10-13T00:00:01.000Z"):
    return AttemptRecord(call_id, logical_id, number, session, start, end, 1000, status,
                         None, None, terminal, "a" * 64, raw)


def final(lid="logical", status="ok", calls=("call",)):
    return FinalRecord(lid, status, None, False, [],
                       [CallRecord(cid, 0, status, None, [], "a" * 64, None, None, None) for cid in calls])


def test_cost_fixtures_through_record_io_and_cost(tmp_path):
    cases = json.loads((Path(__file__).parents[1] / "fixtures/scoring/cost.json").read_text())["cases"]
    for case in cases:
        attempts = [AttemptRecord.from_dict(a) for a in case["attempts"]]
        finals = [final(lid, status, sorted({a.call_id for a in attempts if a.logical_id == lid}))
                  for lid, status in case["logical_statuses"].items()]
        a_path, f_path = tmp_path / "attempts.jsonl", tmp_path / "final.jsonl"
        a_path.write_bytes(b"".join(record_line(a) for a in attempts))
        f_path.write_bytes(b"".join(record_line(f) for f in finals))
        attempts, warnings = read_attempts(a_path)
        finals, final_warnings = read_finals(f_path)
        assert not warnings and not final_warnings
        before = deepcopy((finals, attempts))
        actual = cost(finals=finals, attempts=attempts, derived_from=case["derived_from"], kind=case["provider"])
        assert actual.to_dict() == case["expected"]
        assert Cost.from_dict(actual.to_dict()) == actual and (finals, attempts) == before


@pytest.mark.parametrize("kind,key", [("b1", "prompt_tokens"), ("systemone", "input_tokens")])
@pytest.mark.parametrize("raw,expected,missing", [
    ("{}", 0, 1), ("broken", 0, 1), ({"b64": "AA=="}, 0, 1), ("[]", 0, 1),
    ('{"usage":null}', 0, 1), ('{"usage":{"KEY":true}}', 0, 1),
    ('{"usage":{"KEY":1.5}}', 0, 1), ('{"usage":{"KEY":"7"}}', 0, 1),
    ('{"usage":{"KEY":7}}', 7, 0), ('{"usage":{"KEY":0}}', 0, 0)])
def test_usage_types_and_explicit_kind(kind, key, raw, expected, missing):
    if isinstance(raw, str):
        raw = raw.replace("KEY", key)
    result = cost(finals=[final()], attempts=[attempt(raw=raw)], derived_from=None, kind=kind)
    assert result.input_tokens == dict(sum=expected, n_calls_missing_usage=missing, n_missing_on_200=missing)


def test_terminal_only_non_200_local_errors_and_retry_denominator():
    attempts = [attempt(raw='{"usage":{"input_tokens":900}}', terminal=False, status=503),
                attempt(raw='{"usage":{"input_tokens":5}}', number=2, status=500),
                attempt(call_id="unfinished", raw='{"usage":{"input_tokens":80}}', terminal=False, status=503)]
    result = cost(finals=[final(status="error", calls=("call", "unfinished", "local"))],
                  attempts=attempts, derived_from=None, kind="systemone")
    assert (result.n_calls, result.n_attempts, result.n_retries) == (3, 3, 1)
    assert result.input_tokens == dict(sum=5, n_calls_missing_usage=2, n_missing_on_200=0)
    assert result.failure == dict(num=1, den=1) and result.latency_ms["n"] == 0


def test_kind_ignores_call_id_and_response_choices():
    raw = '{"choices":[],"usage":{"input_tokens":3,"prompt_tokens":8}}'
    for kind, expected in [("systemone", 3), ("b1", 8)]:
        result = cost(finals=[final(calls=("logical/qid",))],
                      attempts=[attempt(call_id="logical/qid", raw=raw)], derived_from=None, kind=kind)
        assert result.input_tokens["sum"] == expected


@pytest.mark.parametrize("status", ["ok", "error", "truncated", "rejected"])
def test_resume_exclusion_only_for_ok(status):
    attempts = [attempt(terminal=False, status=503), attempt(number=2, session="two")]
    result = cost(finals=[final(status=status)], attempts=attempts, derived_from=None, kind="b1")
    assert result.latency_ms == dict(population="logical_ok", n=0, p50=None, p95=None,
                                     n_excluded_resumed=int(status == "ok"))


def test_empty_derived_stage_and_nested_score_serialization():
    stages = cost_by_stage({"dev": ([], [], "full/run"), "test": ([final()], [attempt()], "full/run")}, "b1")
    assert stages["by_stage"]["dev"] == stages["by_stage"]["test"]
    score = ScoreTable("scores/1", "m", "kosgd", "actions_only", "r", {}, stages)
    data = json.loads(json_bytes(score))
    assert data["cost"]["by_stage"]["test"]["derived_from"] == "full/run"
    assert data["cost"]["by_stage"]["test"]["n_logical"] == 0
    with pytest.raises(ValueError, match="stage"):
        cost_by_stage({"unknown": ([], [], None)}, "b1")


def test_rejects_orphan_attempt_and_missing_derived_marker():
    with pytest.raises(ValueError, match="matching"):
        cost(finals=[], attempts=[attempt()], derived_from=None, kind="b1")
    with pytest.raises(ValueError, match="derived"):
        cost(finals=[replace(final(), derived_from="full/run")], attempts=[], derived_from=None, kind="b1")
