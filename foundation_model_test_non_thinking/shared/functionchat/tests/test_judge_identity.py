"""Execution-owned identity: concurrent workers, retries and repeated entry points."""

import io
import json
from threading import Barrier, Lock, get_ident

import pytest

from shared.functionchat.judge import judge_pilot as pilot
from shared.functionchat.judge import run_judge as runner
from shared.multimodal.tests._runner_fakes import offline_guard


@pytest.fixture
def judge_inputs(monkeypatch, tmp_path):
    offline_guard(monkeypatch)
    monkeypatch.setenv("IDENTITY_TEST_KEY", "synthetic-key")
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    for kind in ("call", "slot", "relevance", "completion"):
        (rubrics / f"rubric_{kind}.txt").write_text("{query}", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    rows = [
        {"serial_num": serial, "type_of_output": "slot", "messages": f"item-{serial}",
         "model_output": {"content": "응답"}, "raw_response": {}, "error": None}
        for serial in (1, 2)
    ]
    (output / "call_decision.json").write_text(json.dumps({"results": rows}), encoding="utf-8")
    return output, ["--results-dir", str(output), "--data-dir", str(rubrics),
                    "--api-key-env", "IDENTITY_TEST_KEY", "--repeats", "2", "--retries", "1"]


def response(model, content=None):
    payload = {
        "model": model, "system_fingerprint": "fp", "provider": "provider",
        "choices": [{"message": {"content": content if content is not None else
                                  json.dumps({"verdict": "pass", "justification_ko": "근거"})}}],
    }
    return io.BytesIO(json.dumps(payload).encode())


def test_workers_share_identity_and_consecutive_main_runs_do_not_leak(monkeypatch, judge_inputs):
    output, args = judge_inputs
    for invocation in ("first", "second"):
        barrier = Barrier(2)
        lock = Lock()
        threads, calls = set(), []

        def urlopen(request, timeout):
            item = json.loads(json.loads(request.data)["messages"][0]["content"])
            with lock:
                threads.add(get_ident())
                calls.append(item)
            # Both real pool workers must reach each repeat before either can return.
            barrier.wait(timeout=5)
            return response(f"{invocation}-{item}")

        monkeypatch.setattr(pilot.urllib.request, "urlopen", urlopen)
        assert runner.main([*args, "--concurrency", "2"]) == 0
        summary = json.loads((output / "judge.json").read_text())
        assert len(threads) == 2
        assert sorted(calls) == ["item-1", "item-1", "item-2", "item-2"]
        assert summary["judge"]["served_identity"] == {
            "model": [f"{invocation}-item-1", f"{invocation}-item-2"],
            "system_fingerprint": ["fp"], "provider": ["provider"],
        }
        assert list(summary["judge"]["served_identity"]) == ["model", "system_fingerprint", "provider"]
        assert [row["verdicts"] for row in summary["records"]] == [["pass", "pass"], ["pass", "pass"]]


def test_identity_reset_preserves_conversion_order_and_snapshot_independence():
    identity = pilot.ServedIdentity()
    identity.record({"model": "stale"})
    identity.reset({"provider": ["p"], "unknown": ["ignored"], "model": [2, "2", "a"],
                    "system_fingerprint": None})
    snapshot = identity.snapshot()
    assert snapshot == {"model": ["2", "a"], "provider": ["p"]}
    assert list(snapshot) == ["model", "provider"]
    snapshot["model"].append("not-recorded")
    identity.record({"model": "z", "provider": "", "system_fingerprint": 0})
    assert identity.snapshot() == {"model": ["2", "a", "z"], "provider": ["p"]}
    assert pilot.ServedIdentity().snapshot() == {}
    identity.reset()
    assert identity.snapshot() == {}


def test_parse_failure_identity_is_retained_before_retry(monkeypatch):
    offline_guard(monkeypatch)
    identity = pilot.ServedIdentity()
    responses = iter([response("invalid-revision", "not-json"), response("valid-revision")])
    monkeypatch.setattr(pilot.urllib.request, "urlopen", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(pilot.time, "sleep", lambda _: None)
    result = pilot.call_judge("prompt", "alias", "synthetic-key", 1, 2, identity=identity)
    assert result["verdict"] == "pass"
    assert identity.snapshot() == {
        "model": ["invalid-revision", "valid-revision"],
        "system_fingerprint": ["fp"], "provider": ["provider"],
    }


def test_pilot_main_owns_a_fresh_identity_per_invocation(monkeypatch, judge_inputs):
    output, args = judge_inputs
    identities = []

    class ObservedIdentity(pilot.ServedIdentity):
        def __init__(self):
            super().__init__()
            identities.append(self)

    monkeypatch.setattr(pilot, "ServedIdentity", ObservedIdentity)
    for invocation in ("first", "second"):
        monkeypatch.setattr(pilot.urllib.request, "urlopen",
                            lambda *args, **kwargs: response(invocation))
        assert pilot.main([*args, "--models", "alias", "--out", str(output / "pilot.json")]) == 0
        assert identities[-1].snapshot()["model"] == [invocation]
    assert len(identities) == 2 and identities[0] is not identities[1]
    assert identities[0].snapshot()["model"] == ["first"]
    assert not hasattr(pilot, "SERVED_IDENTITY")
