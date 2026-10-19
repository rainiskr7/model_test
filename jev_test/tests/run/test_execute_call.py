"""무엇: 공개 실행기 기록 경계 · 입력: 메모리 sink/장애 · 출력: 순서·예외 보존 · 계약 §8-6 N."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from jeveval.io import records
from jeveval.run.executor import execute_call
from tests.run.executor_support import Harness, result


def execute(env, history, record, post, sleep, plan=None):
    """파일을 만들지 않고 검증된 합성 계획의 공개 호출 경계를 실행한다."""
    return execute_call(plan or env.plan, history, cfg=replace(env.cfg, base_url="http://invalid"),
                        measurer=SimpleNamespace(measure=lambda p: env.length), post=post, sleep=sleep,
                        session_id="synthetic", headers={}, timeout=1, policy=env.policy, record=record)


def test_record_returns_before_history_wait_and_next_send(env):
    events, history = [], []

    def post(*args, **kwargs):
        events.append(("post", len(history)))
        return result(503 if not history else 200)

    def record(attempt):
        events.append(("record", len(history)))
        assert attempt.attempt == len(history) + 1

    def sleep(seconds):
        events.append(("sleep", len(history)))
        assert seconds == 1

    _, sent, recovered = execute(env, history, record, post, sleep)
    assert (sent, recovered) == (2, 0)
    assert events == [("post", 0), ("record", 0), ("sleep", 1), ("post", 1), ("record", 1)]


@pytest.mark.parametrize("after_write", [False, True])
def test_record_exception_stops_history_sleep_and_post(env, after_write):
    history, captured, events = [], [], []

    def post(*args, **kwargs):
        events.append("post")
        return result(503)

    def record(attempt):
        if after_write:
            captured.append(attempt)
        raise OSError("record failure")

    with pytest.raises(OSError, match="record failure"):
        execute(env, history, record, post, lambda seconds: events.append("sleep"))
    assert events == ["post"] and history == []
    assert len(captured) == int(after_write)


@pytest.mark.parametrize("after_write", [False, True])
def test_record_failure_never_writes_final(tmp_path, env, monkeypatch, after_write):
    """실제 fsync sink 앞/뒤 장애 모두 다음 전송·잠·final 쓰기를 막는다."""
    h = Harness(tmp_path, env, [result(503), result()])
    original = records.append_record

    def fail(path, row):
        if after_write:
            original(path, row)
        raise OSError("sink failure")

    monkeypatch.setattr(records, "append_record", fail)
    with pytest.raises(OSError, match="sink failure"):
        h.run()
    assert len(h.sent) == 1 and h.waits == []
    assert (tmp_path / "dev/final.jsonl").read_bytes() == b""
    assert len(records.read_attempts(tmp_path / "dev/attempts.jsonl")[0]) == int(after_write)


@pytest.mark.parametrize("mode", ["local", "terminal", "exhausted"])
def test_local_and_recovered_calls_do_not_record(env, make_attempt, mode):
    def forbidden(*args, **kwargs):
        pytest.fail("unexpected record/post/sleep")

    plan, history = env.plan, []
    if mode == "local":
        plan = replace(plan, local_errors=["synthetic"])
    elif mode == "terminal":
        history = [make_attempt(plan)]
    else:
        history = [make_attempt(plan, attempt=i, terminal=False, http_status=503)
                   for i in range(1, env.policy.max_attempts + 1)]
    _, sent, recovered = execute(env, history, forbidden, forbidden, forbidden, plan)
    assert sent == 0 and recovered == int(mode != "local")
