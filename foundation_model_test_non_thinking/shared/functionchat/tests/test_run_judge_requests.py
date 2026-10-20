"""Judge pre-refactor capture; temporary paths/hashes vary (see _r3_runner_fakes)."""

import io
import json
import sys
from types import SimpleNamespace

import pytest

from shared.functionchat.judge import run_judge as runner
from shared.multimodal.tests._runner_fakes import offline_guard, read_json
from shared.multimodal.tests._r3_runner_fakes import assert_capture, capture


@pytest.mark.parametrize("generation_error", [False, True])
def test_main_payload_votes_and_retry_unresolved(monkeypatch, tmp_path, capsys, generation_error):
    offline_guard(monkeypatch)
    monkeypatch.setenv("R3_JUDGE_KEY", "synthetic-key")
    pilot = sys.modules[runner.call_judge.__module__]
    # main이 실행마다 등록부를 소유하므로 전역 monkeypatch가 필요 없다.
    # 요청·재판정·judge.json 캡처 기대값은 전역 구현 때와 동일하게 유지한다.
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    for kind in ("call", "slot", "relevance", "completion"):
        (rubrics / f"rubric_{kind}.txt").write_text(
            kind + "\n{tools}\n{query}\n{ground_truth}\n{response}\n", encoding="utf-8")
    output = tmp_path / "synthetic-output"
    output.mkdir()
    for name, kind in [("call_decision", "slot"), ("dialog", "completion")]:
        rows = [{"serial_num": 1, "type_of_output": kind,
                 "tools": [{"name": "도구"}], "messages": [{"role": "user", "content": "질문"}],
                 "ground_truth": "정답", "model_output": {"content": "응답", "tool_calls": []},
                 "raw_response": {}, "error": None}]
        if generation_error and name == "dialog":
            rows.append({"serial_num": 2, "type_of_output": "relevance", "error": "generation failed"})
        rows.append({"serial_num": 3, "type_of_output": "call"})  # deliberately skipped
        (output / (name + ".json")).write_text(json.dumps({"results": rows}, ensure_ascii=False), encoding="utf-8")

    calls, sleeps = [], []
    state = SimpleNamespace(calls=calls, constructors=[], sleeps=sleeps)
    outcomes = iter(["pass", "pass", "pass", "fail"])
    served = "first"

    def urlopen(request, timeout):
        calls.append({"url": request.full_url, "headers": dict(request.header_items()),
                      "body": request.data.decode(), "timeout": timeout})
        verdict = next(outcomes)
        if isinstance(verdict, Exception):
            raise verdict
        payload = {"model": served, "system_fingerprint": "fp", "provider": "provider",
                   "choices": [{"message": {"content": json.dumps({"verdict": verdict, "justification_ko": "근거"})}}]}
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(pilot.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(pilot.time, "sleep", sleeps.append)
    args = ["--results-dir", str(output), "--data-dir", str(rubrics), "--judge-model", "alias",
            "--api-key-env", "R3_JUDGE_KEY", "--timeout", "4", "--retries", "2", "--concurrency", "1"]
    rc = runner.main([*args, "--repeats", "2"])
    assert rc == 1
    first = read_json(output / "judge.json")
    assert first["records"][0]["verdicts"] == ["pass", "pass"]
    assert first["records"][1]["status"] == "judge_error"
    assert first["overall"]["unstable"] == 1
    captures = [capture(output, rc, state, capsys)]
    calls.clear()
    outcomes = iter([TimeoutError("synthetic timeout"), "fail", "fail", "pass"])
    served = "second"
    rc = runner.main([*args, "--repeats", "3", "--retry-unresolved"])
    assert rc == int(generation_error)
    summary = read_json(output / "judge.json")
    assert summary["records"][0] == first["records"][0]
    assert summary["records"][-1]["verdicts"] == ["fail", "fail", "pass"]
    assert summary["judge"]["served_identity"]["model"] == ["first", "second"]
    assert len(calls) == 4 and sleeps == [1.0]
    assert all("n" not in json.loads(call["body"]) for call in calls)  # repeats are individual HTTP calls
    captures.append(capture(output, rc, state, capsys))
    assert_capture("functionchat_" + str(generation_error).lower(), captures, tmp_path)
