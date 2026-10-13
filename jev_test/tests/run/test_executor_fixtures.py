"""무엇: 고정 fixture 실행기 통합 · 입력: 원본 resume/records · 출력: 복구/거부 · 계약 §5·⑤d R3."""

from dataclasses import replace
import math

import pytest

from jeveval.io import records
from jeveval.types import AttemptRecord
from tests.run.executor_support import Harness, pin_fixture_plans, result


@pytest.mark.parametrize("name", ["completed_id", "terminal_recovery", "duplicate_id"])
def test_existing_final_fixtures(tmp_path, env, fixture_json, monkeypatch, name):
    """실제 실행기로 skip·중복 거부·terminal 복구의 정확한 final을 검사한다."""
    source = fixture_json(f"resume/{name}.json")
    h = Harness(tmp_path, env)
    for key in ("attempts_jsonl", "final_jsonl"):
        if key in source:
            (tmp_path / "dev" / key.replace("_jsonl", ".jsonl")).write_text(source[key])
    if name == "duplicate_id":
        with pytest.raises(ValueError, match="duplicate"):
            h.run()
    else:
        if name == "terminal_recovery":
            pin_fixture_plans(monkeypatch, source["expected"]["final"]["calls"][0]["request_sha256"])
        summary = h.run()
        assert summary.n_sent == 0
        if name == "completed_id":
            assert summary.n_skipped_final == 1 and not h.measured
        else:
            final = records.read_finals(tmp_path / "dev/final.jsonl")[0][0]
            assert final.to_dict() == source["expected"]["final"]
            assert summary.n_recovered == 1
    assert h.sent == []


@pytest.mark.parametrize("index", [0, 1, 2])
def test_retry_budget_fixture(tmp_path, env, fixture_json, monkeypatch, index):
    """기존 세 사례의 누적 번호·남은 예산·B1 호출별 복구를 그대로 실행한다."""
    case = fixture_json("resume/retry_budget.json")["cases"][index]
    expected = case["expected"]
    h = Harness(tmp_path, env, [result(503)] * expected["remaining_attempts"])
    for row in case["attempts"]:
        records.append_record(tmp_path / "dev/attempts.jsonl", AttemptRecord.from_dict(row))
    pin_fixture_plans(monkeypatch, case["attempts"][0]["request_sha256"])
    kwargs = {}
    if index == 2:
        kwargs = dict(items=[replace(env.item, questions=[replace(env.q, id=q) for q in ("q1", "q2")])],
                      cfg=replace(env.bcfg, base_url="http://127.0.0.1:1"))
    summary = h.run(**kwargs)
    assert summary.n_sent == expected["remaining_attempts"]
    rows = records.read_attempts(tmp_path / "dev/attempts.jsonl")[0]
    new = rows[len(case["attempts"]):]
    if new:
        assert new[0].attempt == expected["next_attempt"] and new[-1].attempt == 5
        assert new[-1].terminal and len(h.waits) == len(new) - 1
    if index == 1:
        final = records.read_finals(tmp_path / "dev/final.jsonl")[0][0]
        assert (final.status, final.reason) == (expected["status"], expected["reason"])
    if index == 2:
        assert summary.n_recovered == len(expected["recover_call_ids"])
        assert {r.call_id for r in new} == set(expected["retry_call_ids"])


def test_b1_partial_fixture_shape(tmp_path, env, fixture_json, b1_raw):
    """R3: 상태·사유·답 키만 비교하고 합성 해시/원분포/실수 직렬화는 비교하지 않는다."""
    source = next(c["record"] for c in fixture_json("records/roundtrip.json")["cases"]
                  if c["name"] == "b1_partial")
    item = replace(env.item, group_id="g", item_id="b1_partial",
                   questions=[replace(env.q, id=q) for q in ("ready", "other")])
    good = [{"token": "A", "logprob": math.log(.8)}, {"token": "B", "logprob": math.log(.2)}]
    h = Harness(tmp_path, env, [result(raw=b1_raw(good)), result(raw=b1_raw(good[:1]))])
    h.run(items=[item], cfg=replace(env.bcfg, base_url="http://127.0.0.1:1"))
    final = records.read_finals(tmp_path / "dev/final.jsonl")[0][0]
    assert (final.status, final.reason) == (source["status"], source["reason"])
    for actual, expected in zip(final.calls, source["calls"], strict=True):
        assert (actual.call_id, actual.status, actual.reason) == (
            expected["call_id"], expected["status"], expected["reason"])
        assert (None if actual.answers_parsed is None else set(actual.answers_parsed)) == (
            None if expected["answers_parsed"] is None else set(expected["answers_parsed"]))
