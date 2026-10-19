"""Test-only alternative when the sandbox forbids binding loopback sockets.

Runs existing modules unchanged. Only network transports and subprocess launch
are substituted; this does NOT count as the C6.1 HTTP integration check.
"""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import patch

from . import artifacts, execution, http_preflight


def response(state, kind):
    state.calls.append((state.track, kind))
    broken = state.fault == (state.track, kind)
    if kind == "models":
        return {"data": [{"id": "wrong-model" if broken else state.model}]}
    return {"id": "memory", "object": "chat.completion", "created": 0, "model": state.model,
            "choices": [] if broken else [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "A"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


def client(state, **kwargs):
    from openai.types.chat import ChatCompletion
    return SimpleNamespace(max_retries=0,
        models=SimpleNamespace(list=lambda **kw: SimpleNamespace(
            data=[SimpleNamespace(**entry) for entry in response(state, "models")["data"]])),
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw:
            ChatCompletion.model_validate(response(state, "chat")))))


def post(state, *args, **kwargs):
    value = response(state, "chat")
    return SimpleNamespace(status_code=200, headers={}, text=json.dumps(value),
                           raise_for_status=lambda: None, json=lambda: value)


def invoke(ctx, track, argv, result):
    stream = io.StringIO()
    rc = 0
    previous, cwd = sys.modules.pop(argv[3], None), os.getcwd()
    try:
        os.chdir(ctx.base)
        with patch.dict("os.environ", ctx.env, clear=True), patch.object(sys, "argv", [argv[3]] + argv[4:]):
            with redirect_stdout(stream), redirect_stderr(stream):
                try:
                    runpy.run_module(argv[3], run_name="__main__")
                except SystemExit as exc:
                    rc = exc.code or 0
                except Exception as exc:
                    rc = 1
                    print(f"{type(exc).__name__}: {exc}")
    finally:
        os.chdir(cwd)
        if previous is not None:
            sys.modules[argv[3]] = previous
    result["runner_rc"] = rc
    (ctx.base / "logs/smoke" / ctx.stamp / (track + ".runner.log")).write_text(stream.getvalue())
    return rc


def exercise(root, state):
    from .offline_checks import exercise as check
    # No sockets may connect, even if a third-party library ignores offline flags.
    with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
        with patch("openai.OpenAI", side_effect=lambda **kw: client(state, **kw)):
            with patch("requests.post", side_effect=lambda *a, **kw: post(state, *a, **kw)):
                with patch.object(http_preflight, "request", side_effect=lambda ctx, path, payload=None:
                                  response(state, "models" if payload is None else "chat")):
                    with patch.object(execution, "invoke", side_effect=invoke):
                        return check(root, state)


def main():
    from .offline_checks import fixture
    root = fixture(Path(__file__).resolve().parents[2], "127.0.0.1:1")
    os.environ["SMOKE_FIXTURE_HOST"] = "127.0.0.1:1"
    state = SimpleNamespace(model="qwen_qwen3.5_27b_fp8", key="synthetic-smoke-key")
    reports = exercise(root, state)
    output = root / "memory-summary.json"
    output.write_text(json.dumps(reports, indent=2))
    print(output)


if __name__ == "__main__":
    main()
