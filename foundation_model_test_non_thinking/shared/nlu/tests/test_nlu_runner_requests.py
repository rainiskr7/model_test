"""main -> real get_response -> fake HTTP -> real atomic writer.

Variable fields excluded from value comparisons: run.started_at, run.completed_at.
NLU writes UTF-8, indent=2, without a final newline. main returns None on success;
on failure it re-raises (no own stderr); the Python entry point exits with rc=1.
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest
import requests

RUNNER = Path(__file__).resolve().parents[1] / "nlu-gpustack.py"
MODEL = "test/model-a:1"
ENDPOINT = "http://unused.invalid/v1/chat/completions"
PROMPT = "합성 질문\n"
ADDENDUM = (
    "\n\n=========\n\n답변을 평소대로 자유롭게 작성한 뒤, 맨 마지막에 아래 블록을 그대로 덧붙여라.\n"
    "블록 안에는 각 항목마다 제시된 라벨 중 **하나만** 적는다. 설명은 블록 밖에 쓴다.\n\n"
    "[ANSWER]\ncarwash_choice: walk | drive | depends    # 걸어갈지 운전해서 갈지\n[/ANSWER]"
)
CONSTRAINTS = {
    "unsupported_sampling_params": [], "max_output_tokens": None,
    "force_skip_special_tokens": None,
}
FAILURES = {
    "400": "HTTPError: 400 Client Error: Bad Request for url: " + ENDPOINT,
    "503": "HTTPError: 503 Server Error: Service Unavailable for url: " + ENDPOINT,
    "timeout": "Timeout: synthetic timeout",
    "non_json": "JSONDecodeError: Expecting value: line 1 column 1 (char 0)",
}


def deny_network(*args, **kwargs):
    pytest.fail("unexpected live network call")


def prepare(monkeypatch, tmp_path, outcome="ok", *, constrained=False, contract=True, fail_at=2):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MODEL_TEST_BASE", str(tmp_path))
    monkeypatch.setenv("EVAL_TIMESTAMP", "r2-session")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key")
    for name in tuple(os.environ):
        if name.startswith("SERVING_"):
            monkeypatch.delenv(name)
    if constrained:
        monkeypatch.setenv("SERVING_UNSUPPORTED_SAMPLING_PARAMS", "temperature,top_p")
        monkeypatch.setenv("SERVING_MAX_OUTPUT_TOKENS", "64")
        monkeypatch.setenv("SERVING_FORCE_SKIP_SPECIAL_TOKENS", "false")
    # cwd alone is insufficient: dotenv searches ancestors / the source tree.
    monkeypatch.setitem(sys.modules, "dotenv", SimpleNamespace(load_dotenv=lambda: None))
    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "getaddrinfo", deny_network)
    monkeypatch.setattr(requests.sessions.Session, "request", deny_network)
    monkeypatch.setattr(sys, "path", sys.path[:])
    spec = importlib.util.spec_from_file_location("r2_nlu_runner", RUNNER)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "carwash.yaml").write_text(PROMPT, encoding="utf-8")
    (prompts / "jjajangmyeon.yaml").write_text("두 번째 질문", encoding="utf-8")
    monkeypatch.setattr(runner, "PROMPT_DIR", prompts)
    argv = [str(RUNNER), "--model", MODEL, "--endpoint", ENDPOINT]
    if outcome == "ok":
        argv += ["--prompt", str(prompts / "carwash.yaml")]
    if not contract:
        argv += ["--no-contract"]
    monkeypatch.setattr(sys, "argv", argv)
    calls = []

    def post(**kwargs):
        calls.append(kwargs)
        response = requests.Response()
        response.url = ENDPOINT
        response.status_code = 200
        response._content = json.dumps({
            "choices": [{"message": {"content": "  합성 응답\n"}}],
            "model": "served-model", "id": "response-1", "system_fingerprint": "fp-1",
            "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
        }).encode()
        if len(calls) == fail_at:
            if outcome == "timeout":
                raise requests.Timeout("synthetic timeout")
            if outcome == "non_json":
                response._content = b"not JSON"
            if outcome in ("400", "503"):
                response.status_code = int(outcome)
                response.reason = {"400": "Bad Request", "503": "Service Unavailable"}[outcome]
        return response

    monkeypatch.setattr(requests, "post", post)
    output = tmp_path / "results/test_model_a_1/r2-session/language/nlu"
    return runner, calls, output


def read_json(path):
    raw = path.read_bytes()
    value = json.loads(raw)
    assert raw == json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
    return value


def assert_storage(output, *, failure=None, constrained=False, contract=True, first_failed=False):
    expected_files = {"run.json"} if first_failed else {"run.json", "carwash.json"}
    assert {p.name for p in output.iterdir()} == expected_files
    run = read_json(output / "run.json")
    assert set(run) == {
        "schema_version", "requested_model", "endpoint", "serving_constraints",
        "python_executable", "answer_contract", "expected_prompts", "prompt_identity",
        "completed_prompts", "status", "started_at", "completed_at", "failure",
    }
    assert isinstance(run.pop("started_at"), str)
    assert isinstance(run.pop("completed_at"), str)
    constraints = CONSTRAINTS if not constrained else {
        "unsupported_sampling_params": ["temperature", "top_p"],
        "max_output_tokens": 64, "force_skip_special_tokens": False,
    }
    digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
    identities = {"carwash": digest(PROMPT)}
    if failure:
        identities["jjajangmyeon"] = digest("두 번째 질문")
    # Error runs use --no-contract; successful runs cover the real addendum.
    assert run == {
        "schema_version": 1, "requested_model": MODEL, "endpoint": ENDPOINT,
        "serving_constraints": constraints, "python_executable": sys.executable,
        "answer_contract": {"version": 1, "sha256": {"carwash": digest(ADDENDUM)}} if contract else None,
        "expected_prompts": list(identities), "prompt_identity": identities,
        "completed_prompts": [] if first_failed else ["carwash"], "status": "partial" if failure else "complete",
        "failure": failure,
    }
    if first_failed:
        return
    request = {"model": MODEL, "temperature": 0.0, "max_tokens": 8192, "top_p": None}
    if constrained:
        request = {"model": MODEL, "max_tokens": 64, "skip_special_tokens": False}
    assert read_json(output / "carwash.json") == {
        "model": MODEL, "prompt_file": "prompts/carwash.yaml", "prompt": PROMPT,
        "response": "합성 응답", "prompt_sha256": digest(PROMPT),
        "prompt_sent_sha256": digest(PROMPT + (ADDENDUM if contract else "")),
        "answer_contract": {"version": 1, "sha256": digest(ADDENDUM), "items": ["carwash_choice"]} if contract else None,
        "endpoint": ENDPOINT, "served_identity": {
            "model": "served-model", "id": "response-1", "system_fingerprint": "fp-1",
            "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
        }, "request": request, "serving_constraints": constraints,
    }
    return request


@pytest.mark.parametrize("constrained,contract", [(False, True), (False, False), (True, True)])
def test_main_http_payload_and_storage(monkeypatch, tmp_path, capsys, constrained, contract):
    runner, calls, output = prepare(monkeypatch, tmp_path, constrained=constrained, contract=contract)
    assert runner.main() is None  # Python entry point rc=0, not a main() integer return.
    assert capsys.readouterr().err == ""
    request = assert_storage(output, constrained=constrained, contract=contract)
    assert len(calls) == 1
    call = calls[0]
    assert set(call) == {"url", "headers", "data", "timeout"}
    assert call["url"] == ENDPOINT
    assert call["timeout"] == 600.0
    assert set(call["headers"]) == {"Authorization", "Content-Type", "X-Title"}
    assert call["headers"]["Authorization"].startswith("Bearer ")
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["headers"]["X-Title"] == "NLU Evaluation"
    payload = {**request, "messages": [{"role": "user", "content": PROMPT + (ADDENDUM if contract else "")}]}
    assert json.loads(call["data"]) == payload
    assert "\\ud569" in call["data"]  # requests receives default json.dumps ASCII escaping.


@pytest.mark.parametrize("outcome", list(FAILURES))
@pytest.mark.parametrize("fail_at", [1, 2])
def test_main_http_failure_files(monkeypatch, tmp_path, capsys, outcome, fail_at):
    runner, calls, output = prepare(monkeypatch, tmp_path, outcome, contract=False, fail_at=fail_at)
    with pytest.raises((requests.HTTPError, requests.Timeout, requests.exceptions.JSONDecodeError)) as caught:
        runner.main()
    assert f"{type(caught.value).__name__}: {caught.value}" == FAILURES[outcome]
    assert capsys.readouterr().err == ""
    assert len(calls) == fail_at  # no retry; preserve any earlier successful file.
    assert_storage(output, failure=FAILURES[outcome], contract=False, first_failed=fail_at == 1)


@pytest.mark.parametrize("outcome", ["ok", *FAILURES])
def test_entry_point_rc_and_stderr(tmp_path, outcome):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), outcome, str(tmp_path)],
        cwd=tmp_path, capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == (0 if outcome == "ok" else 1)
    if outcome == "ok":
        assert result.stderr == ""
    else:
        assert result.stderr.startswith("Traceback (most recent call last):\n")
        assert result.stderr.splitlines()[-1] == "requests.exceptions." + FAILURES[outcome]
    assert_storage(tmp_path / "results/test_model_a_1/r2-session/language/nlu",
                   failure=FAILURES.get(outcome), contract=False)


if __name__ == "__main__":
    case, root = sys.argv[1:]
    with pytest.MonkeyPatch.context() as patch:
        module, _, _ = prepare(patch, Path(root), case, contract=False)
        module.main()
