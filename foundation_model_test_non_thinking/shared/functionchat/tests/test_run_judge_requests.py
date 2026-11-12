"""Judge pre-refactor capture; temporary paths/hashes vary (see _r3_runner_fakes)."""

import io
import json
import sys
from types import SimpleNamespace

import pytest

from shared.functionchat.judge import run_judge as runner
from shared.multimodal.tests._runner_fakes import offline_guard, read_json
from shared.multimodal.tests._r3_runner_fakes import assert_capture, capture


@pytest.mark.parametrize("effort,temperature_mode,provider", [("medium", "", "deepinfra/bf16"), ("none", "", "deepinfra/bf16"), ("none", "omit", "deepinfra/bf16"), ("", "omit", "")])
@pytest.mark.parametrize("generation_error", [False, True])
def test_main_payload_votes_and_retry_unresolved(monkeypatch, tmp_path, capsys, generation_error, effort, temperature_mode, provider):
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
    assert first["judge_request"] == {
        "model": "alias", "provider": None, "reasoning_effort": None,
        "max_tokens_requested": None, "max_tokens_effective": 700, "temperature": 0,
    }
    assert first["records"][0]["verdicts"] == ["pass", "pass"]
    assert first["records"][1]["status"] == "judge_error"
    assert first["overall"]["unstable"] == 1
    captures = [capture(output, rc, state, capsys)]
    calls.clear()
    # C5: no requests or file mutations, for both full reruns and partial retries.
    for retry in ([], ["--retry-unresolved"]):
        for field, value in (("model", "other"), ("provider", "deepinfra/bf16"),
                             ("reasoning_effort", "medium"), ("max_tokens_effective", 2000), ("temperature", None), ("temperature_mode", "omit")):
            stored = json.loads(json.dumps(first))
            stored["judge_request"][field] = value
            (output / "judge.json").write_text(json.dumps(stored))
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            with pytest.raises(SystemExit) as rejected:
                runner.main([*args, *retry])
            assert rejected.value.code == 2
            assert calls == [] and before == {p.name: p.read_bytes() for p in output.iterdir()}
        for malformed in ('{', '[]', '{}', '{"judge_request": null}', '{"judge_request": {}}'):
            (output / "judge.json").write_text(malformed)
            with pytest.raises(SystemExit) as rejected:
                runner.main([*args, *retry])
            assert rejected.value.code == 2 and calls == []
            assert (output / "judge.json").read_text() == malformed
    # An old summary has no judge_request; explicit 700 and changed repeats still match.
    legacy = dict(first)
    legacy.pop("judge_request")
    (output / "judge.json").write_text(json.dumps(legacy))
    capsys.readouterr()
    outcomes = iter([TimeoutError("synthetic timeout"), "fail", "fail", "pass"])
    served = "second"
    rc = runner.main([*args, "--repeats", "3", "--retry-unresolved", "--judge-max-tokens", "700"])
    assert rc == int(generation_error)
    summary = read_json(output / "judge.json")
    assert summary["judge_request"] == {**first["judge_request"], "max_tokens_requested": 700}
    assert summary["records"][0] == first["records"][0]
    assert summary["records"][-1]["verdicts"] == ["fail", "fail", "pass"]
    assert summary["judge"]["served_identity"]["model"] == ["first", "second"]
    assert len(calls) == 4 and sleeps == [1.0]
    assert all("n" not in json.loads(call["body"]) for call in calls)  # repeats are individual HTTP calls
    captures.append(capture(output, rc, state, capsys))
    # Keep HEAD request bytes and every existing artifact field as the baseline.
    for captured in captures:
        saved = json.loads(captured["files"]["judge.json"])
        saved.pop("judge_request")
        captured["files"]["judge.json"] = json.dumps(saved, ensure_ascii=False, indent=2)
    assert_capture("functionchat_" + str(generation_error).lower(), captures, tmp_path)
    # C2: all optional values travel from the actual parser to HTTP JSON.
    (output / "judge.json").unlink()
    calls.clear()
    outcomes = iter(([TimeoutError("synthetic retry")] if temperature_mode else []) + ["pass"] * 8)
    profile = ["--judge-model", "openai/gpt-oss-120b", "--judge-provider", provider,
               "--judge-reasoning-effort", effort, "--judge-max-tokens", "2000",
               "--judge-temperature-mode", temperature_mode]
    for _ in range(2):
        assert runner.main([*args, *profile, "--repeats", "2"]) == int(generation_error)
    assert len(calls) == 8 + bool(temperature_mode)
    if temperature_mode:
        assert calls[0]["body"] == calls[1]["body"]
    for call in calls:
        body = json.loads(call["body"])
        assert body["model"] == "openai/gpt-oss-120b" and body["max_tokens"] == 2000
        assert body.get("provider") == ({"order": [provider], "allow_fallbacks": False, "require_parameters": True} if provider else None)
        assert body.get("reasoning") == ({"effort": effort} if effort else None)
        assert ("temperature" not in body) is bool(temperature_mode)
        assert "seed" not in body and "extra_body" not in body
    assert read_json(output / "judge.json")["judge_request"] == {
        "model": "openai/gpt-oss-120b", "provider": provider or None, "reasoning_effort": effort or None,
        "max_tokens_requested": 2000, "max_tokens_effective": 2000, "temperature": None if temperature_mode else 0,
        **({"temperature_mode": "omit"} if temperature_mode else {}),
    }
    saved_profile = (output / "judge.json").read_bytes()
    calls.clear()
    for retry in ([], ["--retry-unresolved"]):
        with pytest.raises(SystemExit) as rejected:
            runner.main([*args, *profile, "--judge-temperature-mode", "" if temperature_mode else "omit", *retry])
        assert rejected.value.code == 2 and calls == []
        assert (output / "judge.json").read_bytes() == saved_profile
    for invalid in (["--judge-model", ""], ["--judge-max-tokens", "0"],
                    ["--judge-max-tokens", "-1"], ["--judge-reasoning-effort", "invalid"], ["--judge-reasoning-effort", "xhigh"],
                    *(["--judge-temperature-mode", value] for value in ("0.5", "OMIT", "default")),
                    *(["--judge-cohort", value] for value in ("Oss", "a b", ".", "a/b", "a" * 33, "a\n"))):
        with pytest.raises(SystemExit) as rejected:
            runner.main([*args, *invalid])
        assert rejected.value.code == 2 and calls == []

    # A distinct filename bypasses only the other file's profile, never its own.
    original = {p.name: p.read_bytes() for p in output.iterdir()}
    outcomes = iter(["pass", "pass", "pass", "fail"])
    cohort_args = [*args, "--judge-cohort", "oss", "--judge-temperature-mode", temperature_mode,
                   "--judge-reasoning-effort", effort]
    assert runner.main([*cohort_args, "--repeats", "2"]) == 1
    assert len(calls) == 4
    assert {p.name for p in output.iterdir()} == set(original) | {"judge.oss.json"}
    assert all((output / name).read_bytes() == value for name, value in original.items())
    cohort_path = output / "judge.oss.json"
    first_cohort = read_json(cohort_path)
    assert "judge_cohort" not in first_cohort
    assert first_cohort["judge_request"]["model"] == "alias"
    calls.clear()
    for retry in ([], ["--retry-unresolved"]):
        for stored in (json.dumps({**first_cohort, "judge_request": {
                **first_cohort["judge_request"], "model": "other"}}), "{", "[]"):
            cohort_path.write_text(stored)
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            with pytest.raises(SystemExit) as rejected:
                runner.main([*cohort_args, *retry])
            assert rejected.value.code == 2 and calls == []
            assert before == {p.name: p.read_bytes() for p in output.iterdir()}
    cohort_path.write_text(json.dumps(first_cohort))
    outcomes = iter(["fail", "fail", "pass"])
    assert runner.main([*cohort_args, "--retry-unresolved", "--repeats", "3"]) == int(generation_error)
    assert len(calls) == 3
    retried = read_json(cohort_path)
    assert retried["records"][0] == first_cohort["records"][0]
    assert retried["records"][-1]["verdicts"] == ["fail", "fail", "pass"]
    assert all((output / name).read_bytes() == value for name, value in original.items())
