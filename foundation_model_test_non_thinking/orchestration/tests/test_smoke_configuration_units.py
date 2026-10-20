"""Loader diagnostics and pre-track smoke reports, with no HTTP or real credentials."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from orchestration.smoke import configuration as config_module, main
from orchestration.smoke.isolation import Unavailable

CONF = ("CONFIG=missing_model\nHOST_ENV=SMOKE_UNIT_HOST\nHOST_DEFAULT=fixture.invalid:1\n"
        "KEYVAR=FIXTURE_KEY\nLANE_DISPLAY=fixture\nLANE_TOKENIZER=unused\n")


@pytest.fixture
def configured(tmp_path, monkeypatch):
    root, base = tmp_path / "code", tmp_path / "base"
    (root / "orchestration/models").mkdir(parents=True)
    (root / "orchestration/tracks").mkdir()
    (root / "orchestration/tracks/kmmlu.sh").write_text("# registry only\n")
    (root / "orchestration/models/sample.conf").write_text(CONF)
    (root / ".env").write_text("FIXTURE_KEY=synthetic-smoke-key\n")
    base.mkdir()
    monkeypatch.delenv("SMOKE_UNIT_HOST", raising=False)
    return root, base


def test_configuration_raises_reason_before_parsing_partial_stdout(configured, monkeypatch):
    root, base = configured
    proc = Mock(return_value=SimpleNamespace(returncode=7, stdout="not shell output",
                                             stderr="config 없음: synthetic-smoke-key\n"))
    monkeypatch.setattr(config_module.subprocess, "run", proc)
    env = {}
    with pytest.raises(Unavailable) as caught:
        config_module.configuration(root, base, env, "stamp", "sample")
    assert str(caught.value) == ("model config loader failed (CONFIG=missing_model, rc=7)\n"
                                 "config 없음: ***")
    command = proc.call_args.args[0]
    assert command == [str(base / ".venv/bin/python"), "-B",
                       str(root / "configs/load_model_config.py"), "missing_model"]
    assert proc.call_args.kwargs == dict(env=env, cwd=base, capture_output=True, text=True)
    assert env["OPENAI_API_KEY"] == "synthetic-smoke-key"
    assert "MODEL" not in env
    assert not list(base.iterdir())


def test_success_ignores_stderr_and_keeps_exports(configured, monkeypatch):
    root, base = configured
    monkeypatch.setattr(config_module.subprocess, "run", Mock(return_value=SimpleNamespace(
        returncode=0, stdout="export MODEL='fixture model'\nunset STALE\n", stderr="success notice\n")))
    env = {"STALE": "remove"}
    ctx = config_module.configuration(root, base, env, "stamp", "sample")
    assert ctx.model == "fixture model" and ctx.env is env and "STALE" not in env
    assert ctx.config == "missing_model" and ctx.endpoint == "http://fixture.invalid:1/v1"
    assert not list(base.iterdir())


@pytest.mark.parametrize("stderr,body", [("", "(no loader stderr)"),
    ("\n\t\r", "(no loader stderr)"), ("한글 원인", "한글 원인"),
    ("한글 원인\n\n", "한글 원인"), ("a\x00\x1b\r\tb\x7f", "a    b")])
def test_empty_unicode_and_control_diagnostics(stderr, body):
    reason = config_module.loader_failure_reason("fixture", 7, stderr, {})
    assert reason == f"model config loader failed (CONFIG=fixture, rc=7)\n{body}"


def test_redaction_precedes_control_cleanup_and_line_tail():
    secret = "head\ntail\x1b"
    raw = "old\n" * 25 + secret + "\n" + "last\n" * 19
    reason = config_module.loader_failure_reason("conf\n" + secret, 7, raw,
                                                {"OPENAI_API_KEY": secret})
    header, body = reason.split("\n", 1)
    assert header == "model config loader failed (CONFIG=conf ***, rc=7)"
    assert body == "[truncated] ***\n" + "\n".join(["last"] * 19)
    assert "head" not in body and "tail" not in body and "\x1b" not in reason


def test_redaction_precedes_character_limit():
    secret = "sensitive-prefix-sensitive-suffix"
    raw = "old" * 2000 + secret + "한" * 4080
    reason = config_module.loader_failure_reason("fixture", 7, raw, {"OPENAI_API_KEY": secret})
    body = reason.split("\n", 1)[1]
    assert len(body) == 4096 and body.startswith("[truncated] ")
    assert body.endswith("한" * 4080)
    assert "sensitive" not in body and "suffix" not in body


@pytest.mark.parametrize("keys", [{}, {"OPENAI_API_KEY": ""},
    {"OPENAI_API_KEY": "key", "TAUBENCH_USER_API_KEY": "key-long"},
    {"OPENAI_API_KEY": "key-long", "TAUBENCH_USER_API_KEY": "key"}])
def test_empty_and_overlapping_keys(keys):
    reason = config_module.loader_failure_reason("key-long", 1, "key key-long", keys)
    if any(keys.values()):
        assert reason == "model config loader failed (CONFIG=***, rc=1)\n*** ***"
    else:
        assert reason == "model config loader failed (CONFIG=key-long, rc=1)\nkey key-long"


def test_literal_secret_and_config_length_bound():
    secret = "key[*]?\\value"
    reason = config_module.loader_failure_reason(secret + "x" * 1000, 7, secret,
                                                {"OPENAI_API_KEY": secret})
    header, body = reason.split("\n", 1)
    name = header.split("CONFIG=", 1)[1].rsplit(", rc=", 1)[0]
    assert name.startswith("***") and len(name) == 256 and "[truncated]" in name
    assert body == "***" and secret not in reason


def test_loader_failure_is_top_level_json_reason(configured, tmp_path, monkeypatch, capsys):
    root, base = configured
    monkeypatch.setattr(main, "__file__", str(root / "orchestration/smoke/main.py"))
    monkeypatch.setattr(main, "assemble", lambda root: base)
    monkeypatch.setattr(main, "environment", lambda *args: {})
    run = Mock(side_effect=AssertionError("no track may start"))
    monkeypatch.setattr(main, "run", run)
    monkeypatch.setattr(config_module.subprocess, "run", Mock(return_value=SimpleNamespace(
        returncode=7, stdout="", stderr="config 없음: synthetic-smoke-key\n")))
    output = tmp_path / "summary.json"
    monkeypatch.setattr(main.sys, "argv", ["smoke", "sample", "--out", str(output)])
    assert main.main() == 77
    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert summary == json.loads(output.read_text())
    assert summary == dict(rc=77, status="INCONCLUSIVE", base=str(base), base_kept=True,
        reason="model config loader failed (CONFIG=missing_model, rc=7)\nconfig 없음: ***")
    assert captured.err == "" and "synthetic-smoke-key" not in captured.out + output.read_text()
    run.assert_not_called()
    assert base.exists() and not list(base.iterdir())
