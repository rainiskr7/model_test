"""API judge pre-refactor anchors; variable fields are listed in _r3_runner_fakes."""

from openpyxl import Workbook

from shared.multimodal.tests._runner_fakes import load_runner, read_json
from shared.multimodal.tests._r3_runner_fakes import assert_capture, capture, cli, prepare_local


def test_main_requests_storage_identity(monkeypatch, tmp_path, capsys, fresh_import):
    import argparse
    import json
    import sys
    from unittest.mock import Mock
    import httpx
    import pytest
    from openai import OpenAI

    parse_args = argparse.ArgumentParser.parse_args
    http_send = httpx.Client.send
    runner = load_runner(fresh_import, "koffvqa_api_judge")
    predfile = tmp_path / "synthetic.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.append(["index", "question", "answer", "prediction"])
    sheet.append(["one", "질문", "루브릭", "응답"])
    sheet.append(["two", "질문2", "기준2", "응답2"])
    book.save(predfile)
    state = prepare_local(monkeypatch, tmp_path, ['{"score": 8, "reason": "충족"}', "no JSON"])
    arguments = ["--predfile", str(predfile), "--target-model", "target", "--judge-model", "alias",
                      "--judge-base-url", "http://unused.invalid/v1/chat/completions", "--judge-api-key", "synthetic-key",
                      "--seed", "7", "--judge-max-tokens", "37"]
    cli(monkeypatch, arguments)
    # C7: incomplete judging now fails after preserving both saved artifacts.
    rc = runner.main()
    assert rc == 10
    output = tmp_path / "results/target/r3-session/vision/multimodal/koffvqa_api_judge"
    summary = read_json(output / "summary.json")
    assert summary["judge_request"] == {
        "model": "alias", "provider": None, "reasoning_effort": None,
        "max_tokens_requested": 37, "max_tokens_effective": 37, "temperature": 0.0, "seed": 7,
    }
    assert summary["judge_served_identity"] == {"model": ["served"], "system_fingerprint": ["fp"], "provider": ["provider"]}
    assert (summary["total"], summary["scored"], summary["avg_score"]) == (2, 1, 8.0)
    captured = capture(output, rc, state, capsys)
    saved = json.loads(captured["files"]["summary.json"])
    saved.pop("judge_request")
    captured["files"]["summary.json"] = json.dumps(saved, ensure_ascii=False, indent=2)
    assert_capture("koffvqa_judge", captured, tmp_path)
    state.calls.clear()
    state.constructors.clear()
    for field, value in (("model", "other"), ("provider", "deepinfra/bf16"),
                         ("reasoning_effort", "medium"), ("max_tokens_effective", 2000), ("seed", 8)):
        stored = json.loads(json.dumps(summary))
        stored["judge_request"][field] = value
        (output / "summary.json").write_text(json.dumps(stored))
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        assert runner.main() == 2
        assert state.calls == state.constructors == []
        assert before == {p.name: p.read_bytes() for p in output.iterdir()}
    for malformed in ('{', '[]', '{}', '{"judge_request": null}', '{"judge_request": {}}'):
        (output / "summary.json").write_text(malformed)
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        assert runner.main() == 2
        assert state.calls == state.constructors == []
        assert before == {p.name: p.read_bytes() for p in output.iterdir()}
    (output / "summary.json").unlink()
    before = (output / "results.json").read_bytes()
    assert runner.main() == 2  # orphan rows must not be overwritten without identity
    assert (output / "results.json").read_bytes() == before and state.calls == []

    # Real SDK serialization through an in-memory HTTP transport; no sockets.
    from shared.multimodal.benches import common
    handler = Mock(side_effect=[httpx.Response(200, json={
        "id": "fixture", "object": "chat.completion", "created": 0, "model": "served",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {
            "role": "assistant", "content": '{"score": 8, "reason": "ok"}'}}],
    }) for _ in range(12)])
    with OpenAI(api_key="synthetic", base_url="http://unused.invalid/v1", max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(handler))) as client:
        monkeypatch.setattr(client._client, "send", http_send.__get__(client._client, httpx.Client))
        monkeypatch.setattr(sys.modules[common.make_client.__module__], "OpenAI", Mock(return_value=client))
        # C5: a legacy summary and a run_config-only record both permit full rejudging.
        legacy = dict(summary)
        legacy.pop("judge_request")
        (output / "summary.json").write_text(json.dumps(legacy))
        assert runner.main() == 0
        for index, call in enumerate(handler.call_args_list):
            body = json.loads(call.args[0].content)
            assert body == captured["calls"][index]
        (output / "summary.json").unlink()
        (output / "run_config.json").write_text(json.dumps(summary["run_config"]))
        assert runner.main() == 0
        for path in output.iterdir():
            path.unlink()
        monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_args)
        profile = ["--judge-model", "openai/gpt-oss-120b", "--judge-provider", "deepinfra/bf16",
                   "--judge-reasoning-effort", "medium", "--judge-max-tokens", "2000"]
        cli(monkeypatch, [*arguments, *profile])
        monkeypatch.setenv("SERVING_UNSUPPORTED_SAMPLING_PARAMS", "seed,temperature")
        monkeypatch.setenv("SERVING_MAX_OUTPUT_TOKENS", "5")
        for _ in range(2):
            assert runner.main() == 0
        for call in handler.call_args_list[4:]:
            body = json.loads(call.args[0].content)
            assert body["model"] == "openai/gpt-oss-120b" and body["max_tokens"] == 2000
            assert body["provider"] == {"order": ["deepinfra/bf16"], "allow_fallbacks": False, "require_parameters": True}
            assert body["reasoning"] == {"effort": "medium"} and body["seed"] == 7
            assert "extra_body" not in body
        final = read_json(output / "summary.json")
        assert final["judge_request"] == {
            "model": "openai/gpt-oss-120b", "provider": "deepinfra/bf16", "reasoning_effort": "medium",
            "max_tokens_requested": 2000, "max_tokens_effective": 2000, "temperature": 0.0, "seed": 7,
        }
        assert final["run_config"]["decoding"] == {"temperature": 0.0, "max_tokens": 2000, "seed": 7}
        assert final["run_config"]["serving_constraints"]["removed_parameters"] == []
        for invalid in (["--judge-model", ""], ["--judge-max-tokens", "0"],
                        ["--judge-max-tokens", "-1"], ["--judge-reasoning-effort", "invalid"]):
            monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_args)
            cli(monkeypatch, [*arguments, *invalid])
            with pytest.raises(SystemExit) as rejected:
                runner.main()
            assert rejected.value.code == 2
        assert handler.call_count == 8
        # C1/C5: omitted and explicit 1024 have identical full-lane request bodies.
        for path in output.iterdir():
            path.unlink()
        for tokens in ([], ["--judge-max-tokens", "1024"]):
            monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_args)
            cli(monkeypatch, [*arguments[:-2], "--seed", "0", *tokens])
            assert runner.main() == 0
            request = read_json(output / "summary.json")["judge_request"]
            assert request["max_tokens_requested"] == (1024 if tokens else None)
            assert request["max_tokens_effective"] == 1024 and request["seed"] == 0
        for index, call in enumerate(handler.call_args_list[8:]):
            assert json.loads(call.args[0].content) == {**captured["calls"][index % 2], "seed": 0, "max_tokens": 1024}
        assert handler.call_count == 12
