"""API judge pre-refactor anchors; variable fields are listed in _r3_runner_fakes."""

import pytest
from openpyxl import Workbook

from shared.multimodal.tests._runner_fakes import load_runner, read_json
from shared.multimodal.tests._r3_runner_fakes import assert_capture, capture, cli, prepare_local


@pytest.mark.parametrize("effort,temperature_mode,provider", [("medium", "", "deepinfra/bf16"), ("none", "", "deepinfra/bf16"), ("none", "omit", "deepinfra/bf16"), ("", "omit", "")])
def test_main_requests_storage_identity(monkeypatch, tmp_path, capsys, fresh_import, effort, temperature_mode, provider):
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
                         ("reasoning_effort", "medium"), ("max_tokens_effective", 2000), ("seed", 8), ("temperature", None), ("temperature_mode", "omit")):
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
        profile = ["--judge-model", "openai/gpt-oss-120b", "--judge-provider", provider,
                   "--judge-reasoning-effort", effort, "--judge-max-tokens", "2000",
                   "--judge-temperature-mode", temperature_mode]
        cli(monkeypatch, [*arguments, *profile])
        monkeypatch.setenv("SERVING_UNSUPPORTED_SAMPLING_PARAMS", "seed,temperature")
        monkeypatch.setenv("SERVING_MAX_OUTPUT_TOKENS", "5")
        for _ in range(2):
            assert runner.main() == 0
        for call in handler.call_args_list[4:]:
            body = json.loads(call.args[0].content)
            assert body["model"] == "openai/gpt-oss-120b" and body["max_tokens"] == 2000
            assert body.get("provider") == ({"order": [provider], "allow_fallbacks": False, "require_parameters": True} if provider else None)
            assert body.get("reasoning") == ({"effort": effort} if effort else None)
            assert ("temperature" not in body) is bool(temperature_mode)
            assert body["seed"] == 7
            assert "extra_body" not in body
        final = read_json(output / "summary.json")
        assert final["judge_request"] == {
            "model": "openai/gpt-oss-120b", "provider": provider or None, "reasoning_effort": effort or None,
            "max_tokens_requested": 2000, "max_tokens_effective": 2000, "temperature": None if temperature_mode else 0.0, "seed": 7,
            **({"temperature_mode": "omit"} if temperature_mode else {}),
        }
        assert final["run_config"]["decoding"] == {"temperature": None if temperature_mode else 0.0, "max_tokens": 2000, "seed": 7,
                                                    **({"temperature_mode": "omit"} if temperature_mode else {})}
        assert final["run_config"]["decoding_requested"] == final["run_config"]["decoding"]
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_args)
        cli(monkeypatch, [*arguments, *profile, "--judge-temperature-mode", "" if temperature_mode else "omit"])
        assert runner.main() == 2 and handler.call_count == 8
        assert before == {p.name: p.read_bytes() for p in output.iterdir()}
        assert final["run_config"]["serving_constraints"]["removed_parameters"] == []
        for invalid in (["--judge-model", ""], ["--judge-max-tokens", "0"],
                        ["--judge-max-tokens", "-1"], ["--judge-reasoning-effort", "invalid"], ["--judge-reasoning-effort", "xhigh"],
                        *(["--judge-temperature-mode", value] for value in ("0.5", "OMIT", "default")),
                        ["--judge-prompt-profile", "ORIGINAL"], ["--judge-prompt-profile", "unknown"],
                        ["--rejudge-purpose", "MIGRATION"], ["--rejudge-purpose", "diagnostic"]):
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

        # C2: keep legacy summaries/config-only/orphan files untouched on either new option.
        for kind in ("summary", "legacy", "config-only", "orphan"):
            for path in output.iterdir():
                path.unlink()
            stored = dict(summary)
            if kind == "legacy":
                stored.pop("judge_request")
            if kind in ("summary", "legacy"):
                (output / "summary.json").write_text(json.dumps(stored))
            elif kind == "config-only":
                (output / "run_config.json").write_text(json.dumps(summary["run_config"]))
            (output / "results.json").write_text("[]")
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            for flags in (["--judge-prompt-profile", "original"], ["--rejudge-purpose", "migration"]):
                monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_args)
                cli(monkeypatch, [*arguments, *flags])
                assert runner.main() == 2 and handler.call_count == 12
                assert before == {p.name: p.read_bytes() for p in output.iterdir()}
        for path in output.iterdir():
            path.unlink()
        # Real SDK request serialization for original, with common input normalization.
        sheet["B2"] = None
        sheet["C2"] = 42
        sheet["D2"] = None
        book.save(predfile)
        texts = ["근거\n**최종 점수: 10점 만점에 8점**.", "최종 점수: 10점 만점에 11점"]
        handler.side_effect = [httpx.Response(200, json={
            "id": "fixture", "object": "chat.completion", "created": 0, "model": "served",
            "provider": "original-provider",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
        }) for text in texts]
        monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_args)
        cli(monkeypatch, [*arguments, "--judge-prompt-profile", "original", "--rejudge-purpose", "migration"])
        assert runner.main() == 10
        sent = [json.loads(call.args[0].content) for call in handler.call_args_list[-2:]]
        assert sent[0]["messages"] == [{"role": "user", "content": runner.ORIGINAL_JUDGE_PROMPT.format("", "", "42")}]
        assert sent[1]["messages"] == [{"role": "user", "content": runner.ORIGINAL_JUDGE_PROMPT.format("질문2", "응답2", "기준2")}]
        assert sent[0]["temperature"] == 0 and sent[0]["seed"] == 7 and sent[0]["max_tokens"] == 37
        final = read_json(output / "summary.json")
        rows = read_json(output / "results.json")
        assert (final["total"], final["scored"], final["avg_score"]) == (2, 1, 8.0)
        assert final["rejudge_purpose"] == final["run_config"]["extra"]["rejudge_purpose"] == "migration"
        assert final["judge_prompt_profile"] == final["run_config"]["judge"]["prompt_profile"] == "original"
        assert final["judge_prompt_version"] == final["run_config"]["judge"]["prompt_version"] == "koffvqa-original-v1"
        assert final["judge_prompt_template_sha256"] == final["run_config"]["judge"]["prompt_template_sha256"] == runner._prompt_template_hash("original")
        assert rows[0]["score"] == 8 and rows[0]["error"] is None
        assert rows[1]["score"] is None and rows[1]["error"]
        assert [row["reason"] for row in rows] == [row["raw_judge_output"] for row in rows] == texts
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        for flags in (["--judge-prompt-profile", "", "--rejudge-purpose", "migration"],
                      ["--judge-prompt-profile", "original", "--rejudge-purpose", ""]):
            monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_args)
            cli(monkeypatch, [*arguments, *flags])
            assert runner.main() == 2 and handler.call_count == 14
            assert before == {p.name: p.read_bytes() for p in output.iterdir()}

        # Error-only retries validate every input before requesting or overwriting.
        retry_args = [*arguments, "--judge-prompt-profile", "original", "--rejudge-purpose", "migration", "--retry-errors"]
        monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_args)
        cli(monkeypatch, retry_args)
        original_summary = (output / "summary.json").read_bytes()
        original_results = (output / "results.json").read_bytes()
        for name in ("summary.json", "results.json"):
            path = output / name
            content = path.read_bytes()
            path.unlink()
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            assert runner.main() == 2 and handler.call_count == 14
            assert before == {p.name: p.read_bytes() for p in output.iterdir()}
            path.write_bytes(content)
        for field, value in (("judge_prompt_profile", ""), ("rejudge_purpose", ""),
                             ("judge_prompt_version", "changed"), ("judge_prompt_template_sha256", "sha256:changed")):
            changed = json.loads(original_summary)
            changed[field] = value
            (output / "summary.json").write_text(json.dumps(changed))
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            assert runner.main() == 2 and handler.call_count == 14
            assert before == {p.name: p.read_bytes() for p in output.iterdir()}
        for field, value in (("model", "other"), ("provider", "other"), ("reasoning_effort", "none"),
                             ("temperature_mode", "omit"), ("temperature", 0.5),
                             ("max_tokens_effective", 2000), ("seed", 8)):
            changed = json.loads(original_summary)
            changed["judge_request"][field] = value
            (output / "summary.json").write_text(json.dumps(changed))
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            assert runner.main() == 2 and handler.call_count == 14
            assert before == {p.name: p.read_bytes() for p in output.iterdir()}
        for field in ("judge_prompt_version", "judge_prompt_template_sha256"):
            changed = json.loads(original_summary)
            changed.pop(field)
            changed["run_config"]["judge"].pop("prompt_version" if field.endswith("version") else "prompt_template_sha256")
            (output / "summary.json").write_text(json.dumps(changed))
            assert runner.main() == 2 and handler.call_count == 14
        (output / "summary.json").write_bytes(original_summary)
        for field, value in (("idx", 3), ("dataset_item_id", "other"), ("question", "changed"),
                             ("response", "changed"), ("criteria", "changed"), ("score", True)):
            changed = json.loads(original_results)
            changed[0][field] = value
            (output / "results.json").write_text(json.dumps(changed))
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            assert runner.main() == 2 and handler.call_count == 14
            assert before == {p.name: p.read_bytes() for p in output.iterdir()}
        for bad in ("{", "{}", "[]", json.dumps(list(reversed(rows))), json.dumps(rows[:1])):
            (output / "results.json").write_text(bad)
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            assert runner.main() == 2 and handler.call_count == 14
            assert before == {p.name: p.read_bytes() for p in output.iterdir()}

        # Noncanonical whitespace, escaped Korean and extra record fields survive byte-for-byte.
        rows[0]["extra"] = {"preserve": "한글 \\n } [ ,"}
        stable = json.dumps(rows[0], ensure_ascii=True, separators=(", ", " : ")).encode()
        prefix = b'[\r\n\t' + stable + b',\r\n'
        (output / "results.json").write_bytes(prefix + json.dumps(rows[1]).encode() + b'\r\n]\r\n')
        handler.side_effect = [httpx.Response(200, json={
            "id": "fixture", "object": "chat.completion", "created": 0, "model": "retry-served",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
        }) for text in ("^(^^)" * 20, "기준 충족이므로 **최종 점수: 10점 만점에 10점**")]
        assert runner.main() == 10 and handler.call_count == 15
        retry_summary = json.loads((output / "summary.json").read_bytes())
        assert (retry_summary["total"], retry_summary["scored"], retry_summary["avg_score"]) == (2, 1, 8.0)
        assert retry_summary["retry_errors"] == {"count": 1, "history": [[1]]}
        assert (output / "results.json").read_bytes().startswith(prefix)
        assert runner.main() == 0 and handler.call_count == 16
        retry_summary = json.loads((output / "summary.json").read_bytes())
        merged = json.loads((output / "results.json").read_bytes())
        assert (retry_summary["total"], retry_summary["scored"], retry_summary["avg_score"]) == (2, 2, 9.0)
        assert retry_summary["retry_errors"] == {"count": 2, "history": [[1], [1]]}
        assert retry_summary["judge_served_identity"]["model"] == ["retry-served", "served"]
        assert retry_summary["judge_served_identity"]["provider"] == ["original-provider"]
        assert merged[0] == rows[0] and merged[1]["score"] == 10 and merged[1]["error"] is None
        assert [row["idx"] for row in merged] == [0, 1]
        assert (output / "results.json").read_bytes().startswith(prefix)
        assert (output / "results.json").read_bytes().endswith(b'\r\n]\r\n')
        for call in handler.call_args_list[-2:]:
            body = json.loads(call.args[0].content)
            assert body == sent[1]
        before = (output / "results.json").read_bytes()
        assert runner.main() == 0 and handler.call_count == 16
        assert (output / "results.json").read_bytes() == before
        assert json.loads((output / "summary.json").read_bytes())["retry_errors"] == {
            "count": 3, "history": [[1], [1], []]}

        # Omitting the option still rejudges every row and produces no retry metadata.
        handler.side_effect = [httpx.Response(200, json={
            "id": "fixture", "object": "chat.completion", "created": 0, "model": "served",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": "최종 점수: 10점 만점에 5점"}}],
        }) for _ in range(2)]
        monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_args)
        cli(monkeypatch, retry_args[:-1])
        assert runner.main() == 0 and handler.call_count == 18
        assert "retry_errors" not in json.loads((output / "summary.json").read_bytes())

        # The default JSON profile also retries disjoint errors and keeps the middle row.
        for path in output.iterdir():
            path.unlink()
        sheet.append(["three", "질문3", "기준3", "응답3"])
        book.save(predfile)
        handler.side_effect = [httpx.Response(200, json={
            "id": "fixture", "object": "chat.completion", "created": 0, "model": "served",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
        }) for text in ("bad", '{"score": 6, "reason": "middle"}', "bad",
                       '{"score": 2, "reason": "first"}', '{"score": 8, "reason": "last"}')]
        monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_args)
        cli(monkeypatch, [*arguments, "--retry-errors"])
        assert runner.main() == 2 and handler.call_count == 18
        monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_args)
        cli(monkeypatch, arguments)
        assert runner.main() == 10 and handler.call_count == 21
        initial = (output / "results.json").read_bytes()
        middle = initial[initial.index(b'  {', initial.index(b'  }') + 1):initial.rindex(b'  {')]
        monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse_args)
        cli(monkeypatch, [*arguments, "--retry-errors"])
        assert runner.main() == 0 and handler.call_count == 23
        merged = json.loads((output / "results.json").read_bytes())
        assert [row["score"] for row in merged] == [2, 6, 8]
        assert middle in (output / "results.json").read_bytes()
        final = json.loads((output / "summary.json").read_bytes())
        assert final["retry_errors"] == {"count": 1, "history": [[0, 2]]}
        assert (final["total"], final["scored"], final["avg_score"]) == (3, 3, 16 / 3)
