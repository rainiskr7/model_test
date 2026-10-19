"""무엇: 순차 실행 짝 시험 · 입력: 합성 응답 · 출력: 기록 순서·예산·상태 · 계약 §4-2·§5."""

from dataclasses import replace

import pytest

from jeveval.io import records
from jeveval.types import RetryPolicy
from tests.run.executor_support import Harness, result


def test_retries_bytes_wait_fsync_order_and_headers(tmp_path, env, monkeypatch):
    """503 재시도 바이트·주입 값·attempt→final fsync 경계를 함께 검사한다."""
    h = Harness(tmp_path, env, [result(503, retry_after="7"), result(503), result()])
    events, original, real_fsync = [], records.append_record, records.os.fsync

    def sync(fd):
        """각 append의 실제 fsync를 관측한다."""
        events.append("fsync")
        real_fsync(fd)

    def append(path, row):
        """쓰기 앞뒤와 타입을 기록한다."""
        events.append(type(row).__name__)
        original(path, row)

    monkeypatch.setattr(records.os, "fsync", sync)
    monkeypatch.setattr(records, "append_record", append)
    summary = h.run(headers={"Authorization": "secret"}, timeout=17)
    assert summary.to_dict() == dict(n_logical=1, n_skipped_final=0, n_calls=1,
        n_sent=3, n_recovered=0, by_status={"ok": 1}, n_deferred=0)
    assert h.waits == [7, 2]
    assert h.sent == [("http://127.0.0.1:1/v1/systemone", env.plan.body, 17,
                       {"Authorization": "secret"})] * 3
    assert events[-8:] == ["AttemptRecord", "fsync"] * 3 + ["FinalRecord", "fsync"]
    attempts, _ = records.read_attempts(tmp_path / "dev/attempts.jsonl")
    assert [a.attempt for a in attempts] == [1, 2, 3]
    assert [a.terminal for a in attempts] == [False, False, True]
    assert {a.session_id for a in attempts} == {"session-new"}
    assert b"secret" not in (tmp_path / "dev/attempts.jsonl").read_bytes()
    assert b"secret" not in (tmp_path / "dev/final.jsonl").read_bytes()


@pytest.mark.parametrize("responses,status,reason,waits", [
    ([result(503)] * 5, "error", "http_503", [1, 2, 4, 8]),
    ([result(None, transport_error="timeout"), result()], "ok", None, [1]),
    ([result(200, transport_error="transport:IncompleteRead"), result()], "ok", None, [1]),
    ([result(422, "too long")], "rejected", "input_limit", []),
])
def test_policy_and_result_paths(tmp_path, env, responses, status, reason, waits):
    """실행기를 통해 예산 소진·전송 우선 재시도·길이 거부를 확인한다."""
    h = Harness(tmp_path, env, responses)
    summary = h.run()
    final = records.read_finals(tmp_path / "dev/final.jsonl")[0][0]
    assert (final.status, final.reason) == (status, reason)
    assert summary.n_sent == len(responses) and h.waits == waits


def test_local_error_and_measure_failure(tmp_path, env):
    """로컬 오류는 측정/전송 없이 기록하고 측정 예외는 전송 전에 올린다."""
    h = Harness(tmp_path / "local", env)
    summary = h.run(items=[replace(env.item, state_fields=" ")])
    final = records.read_finals(h.root / "dev/final.jsonl")[0][0]
    assert final.reason == "request_contract" and final.calls[0].attempts == 0
    assert summary.n_calls == 1 and summary.n_sent == 0 and not h.measured
    h = Harness(tmp_path / "measure", env)

    def broken(plan):
        """측정 불가 예외를 그대로 주입한다."""
        raise RuntimeError("cannot measure")

    h.measure = broken
    with pytest.raises(RuntimeError, match="cannot measure"):
        h.run()
    assert not h.sent and (h.root / "dev/final.jsonl").read_bytes() == b""


def test_b1_finishes_after_middle_error(tmp_path, env, b1_raw):
    """B1 중간 호출 실패 뒤에도 마지막 호출을 보내며 계획 순서로 기록한다."""
    good = b1_raw([{"token": "A", "logprob": -1}, {"token": "B", "logprob": -2}])
    h = Harness(tmp_path, env, [result(raw=good), result(500), result(raw=good)])
    item = replace(env.item, questions=[replace(env.q, id=q) for q in ("a", "b", "c")])
    summary = h.run(items=[item], cfg=replace(env.bcfg, base_url="http://127.0.0.1:1"))
    final = records.read_finals(tmp_path / "dev/final.jsonl")[0][0]
    assert [c.status for c in final.calls] == ["ok", "error", "ok"]
    assert [c.call_id.rsplit("/", 1)[1] for c in final.calls] == ["a", "b", "c"]
    assert final.reason == "http_500" and summary.n_sent == summary.n_calls == 3
    assert all(s[0].endswith("/v1/chat/completions") for s in h.sent)


def test_empty_stage_and_invalid_arguments(tmp_path, env):
    """빈 단계 파일을 만들되 인자 거부는 파일 생성보다 먼저 수행한다."""
    h = Harness(tmp_path, env)
    for args in ({"stage": "bad"}, {"cfg": env.cfg}, {"policy": replace(env.policy, max_attempts=0)},
                 {"items": [env.item, env.item]}):
        with pytest.raises(ValueError):
            h.run(**args)
        assert not (tmp_path / "dev/final.jsonl").exists()
        assert not (tmp_path / "dev/attempts.jsonl").exists()
    summary = h.run(items=[])
    assert summary.to_dict() == dict(n_logical=0, n_skipped_final=0, n_calls=0,
        n_sent=0, n_recovered=0, by_status={}, n_deferred=0)
    assert (tmp_path / "dev/final.jsonl").read_bytes() == b""
    assert (tmp_path / "dev/attempts.jsonl").read_bytes() == b""


def test_custom_policy_controls_executor_budget_and_wait(tmp_path, env):
    h = Harness(tmp_path, env, [result(429), result(429)])
    policy = RetryPolicy(2, [429], [.25])
    summary = h.run(policy=policy)
    assert summary.n_sent == 2 and h.waits == [.25]
    attempts = records.read_attempts(tmp_path / "dev/attempts.jsonl")[0]
    assert [row.terminal for row in attempts] == [False, True]
    final = records.read_finals(tmp_path / "dev/final.jsonl")[0][0]
    assert final.reason == "http_429" and final.calls[0].attempts == 2
