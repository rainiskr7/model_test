"""Synthetic unit fixtures and pre-extraction subprocess/storage contracts."""

import hashlib
import io
import json
import os
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from shared.taubench.runner import run_taubench as runner


def _inputs(bench, *, empty=False):
    domain = bench / "data/tau2/domains/retail"
    domain.mkdir(parents=True)
    tasks = [
        {"id": "free", "evaluation_criteria": {"reward_basis": ["DB"]}},
        {"id": "judge", "evaluation_criteria": {
            "reward_basis": ["NL_ASSERTION"], "nl_assertions": ["check"]}},
    ]
    (domain / "tasks.json").write_text(json.dumps(tasks), encoding="utf-8")
    (domain / "split_tasks.json").write_text(
        json.dumps({"test": ["judge"] if empty else ["judge", "free"]}), encoding="utf-8"
    )


@pytest.mark.parametrize("empty", [False, True])
def test_load_run_split_selects_judge_free_tasks(tmp_path, empty):
    _inputs(tmp_path, empty=empty)
    args = runner.parse_args(["--model", "candidate", "--domain", "retail", "--split", "test"])
    if empty:
        with pytest.raises(ValueError, match="retail split 'test' has no judge-free runnable tasks"):
            runner._load_run_split(tmp_path, args)
    else:
        split, ids = runner._load_run_split(tmp_path, args)
        assert ids == ["free"]
        assert split == {
            "domain": "retail", "name": "test", "source": "data/tau2/domains/retail/split_tasks.json",
            "task_count": 2, "runnable_task_count": 1, "task_ids": ["free"],
            "not_measured_task_count": 1,
            "not_measured_tasks": [{"task_id": "judge", "reward_basis": ["NL_ASSERTION"],
                                    "reason": "llm_judge_required"}],
        }


@pytest.mark.parametrize("model,expected", [("candidate", "openai/candidate"), ("vendor/model", "vendor/model")])
def test_upstream_env_copies_input_and_preserves_shim_contract(model, expected):
    original = {"OPENAI_API_KEY": "synthetic", "TAU2_DATA_DIR": "old"}
    result = runner._upstream_env(original, Path("/fixture"), "http://unused/v1",
                                  model, Path("/output/record.json"))
    assert result == {
        "OPENAI_API_KEY": "synthetic", "TAU2_DATA_DIR": "/fixture/data",
        "TAUBENCH_CONSTRAINED_API_BASE": "http://unused/v1",
        "TAUBENCH_CANDIDATE_MODEL": expected,
        "TAUBENCH_REMOVED_PARAMS_OUT": "/output/record.json",
        "PYTHONPATH": str(Path(runner.__file__).resolve().parents[3]),
    }
    assert original == {"OPENAI_API_KEY": "synthetic", "TAU2_DATA_DIR": "old"}


@pytest.mark.parametrize("domain", ["telecom", "retail"])
def test_split_summary_preserves_existing_telecom_label(domain):
    args = SimpleNamespace(domain=domain, split="test")
    assert runner._split_summary(args, ["one"], {
        "task_count": 2, "not_measured_task_count": 1,
    }) == "[taubench] telecom split 'test': 1/2 judge-free tasks; 1 not measured"


@pytest.mark.parametrize("external,options,rejected,anchor", [
    (False, [], False, False),
    (True, [], False, False),
    (True, ["--user-provider", "", "--user-reasoning-effort", ""], False, False),
    (True, ["--user-provider", "deepinfra/bf16"], False, False),
    (True, ["--user-reasoning-effort", "low"], False, False),
    (True, ["--user-reasoning-effort", "high"], False, False),
    (True, ["--user-provider", "deepinfra/bf16", "--user-reasoning-effort", "medium"], False, False),
    pytest.param(True, ["--user-provider", "deepinfra/bf16", "--user-reasoning-effort", "medium"],
                 False, True, id="litellm-1.82.6-anchor"),
    (False, ["--user-provider", "deepinfra/bf16"], True, False),
    (False, ["--user-reasoning-effort", "low"], True, False),
    (True, ["--mode", "solo", "--user-provider", "deepinfra/bf16"], True, False),
    (True, ["--mode", "solo", "--user-reasoning-effort", "low"], True, False),
    (True, ["--user-model", "anthropic/user", "--user-provider", "deepinfra/bf16"], True, False),
    (True, ["--user-model", "openai/user", "--user-reasoning-effort", "medium"], True, False),
    (True, ["--user-model", "", "--user-provider", "deepinfra/bf16"], True, False),
    (True, ["--user-base-url", "http://unused/v1", "--user-provider", "deepinfra/bf16"], True, False),
    (True, ["--user-base-url", "http://unused/v1", "--user-reasoning-effort", "low"], True, False),
    (True, ["--user-reasoning-effort", "invalid"], True, False),
    (True, ["--user-provider", "Bad/provider"], True, False),
    (True, ["--user-provider", "two words"], True, False),
    (True, ["--user-provider", "provider\n"], True, False),
    (True, ["--user-provider", "/provider"], True, False),
])
def test_prepare_llm_args_keeps_user_protocol_independent(monkeypatch, external, options, rejected, anchor, tmp_path, capsys):
    """설정부터 CLI·manifest·실제 변환까지의 계약.

    유지: 사용자 지시(새 함수 금지), Stage 4
    """
    monkeypatch.setattr(runner, "_unsupported_sampling_params", lambda: ["temperature"])
    argv = [
        "--model", "candidate", "--mode", "standard", "--user-model",
        "openrouter/user" if external else "local-user",
        "--request-timeout", "3", "--max-tokens", "17",
    ] + options
    if rejected:
        with mock.patch.object(runner.subprocess, "run") as upstream, mock.patch.object(runner.subprocess, "check_output") as git:
            with pytest.raises(SystemExit) as error:
                runner.main(argv)
            assert error.value.code == 2
            stderr = capsys.readouterr().err
            assert stderr and "unrecognized arguments" not in stderr
            upstream.assert_not_called()
            git.assert_not_called()
        return
    args = runner.parse_args(argv)
    runner._validate_args(args)
    environ = {"TAUBENCH_USER_API_KEY": "synthetic"}
    candidate, user, removed = runner._prepare_llm_args(args, "http://unused/v1", environ)
    assert candidate == {"api_base": "http://unused/v1", "timeout": 3.0,
                         "num_retries": 0, "max_tokens": 17}
    expected = ({"timeout": 120.0, "num_retries": 0, "max_tokens": 16384, "temperature": 0.0}
                if external else {"api_base": "http://unused/v1", "timeout": 120.0,
                                  "num_retries": 0, "max_tokens": 16384})
    extra = {}
    if args.user_provider:
        extra["provider"] = {"order": ["deepinfra/bf16"], "allow_fallbacks": False, "require_parameters": True}
    if args.user_reasoning_effort:
        extra["reasoning"] = {"effort": args.user_reasoning_effort}
    if extra:
        expected["extra_body"] = extra
    assert user == expected
    assert json.dumps(user, separators=(",", ":")) == json.dumps(expected, separators=(",", ":"))
    command = runner.build_upstream_command(args, candidate, user, tmp_path, ["one"])
    assert command[command.index("--user-llm-args") + 1] == json.dumps(expected, separators=(",", ":"))
    assert removed == ([] if external else ["temperature"])
    assert environ == ({"TAUBENCH_USER_API_KEY": "synthetic", "OPENROUTER_API_KEY": "synthetic"}
                       if external else {"TAUBENCH_USER_API_KEY": "synthetic"})
    for base_set in (False, True):
        if base_set:
            monkeypatch.setenv("OPENROUTER_API_BASE", "http://override.invalid/v1")
        else:
            monkeypatch.delenv("OPENROUTER_API_BASE", raising=False)
        integrity = runner._build_manifest(args, {}, "http://unused/v1", user, [], removed)["harness_integrity"]
        for key in ("user_provider", "user_reasoning_effort"):
            if getattr(args, key):
                assert integrity[key] == getattr(args, key)
            else:
                assert key not in integrity
        if extra:
            assert integrity["user_openrouter_api_base_set"] is base_set
        else:
            assert "user_openrouter_api_base_set" not in integrity
        assert "http://override.invalid/v1" not in json.dumps(integrity)

    # Execute the actual shell wrapper with a recording interpreter, wholly in tmp_path.
    root = Path(runner.__file__).resolve().parents[3]
    (tmp_path / "data/tau2-bench").mkdir(parents=True)
    interpreter = tmp_path / "record-python"
    interpreter.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding="utf-8")
    interpreter.chmod(0o755)
    wrapper = subprocess.run(["/bin/bash", str(root / "shared/taubench/run_taubench.sh"), "candidate"],
        env={"PATH": os.defpath, "MODEL_TEST_BASE": str(tmp_path), "TAU_PY": str(interpreter),
             "EVAL_TIMESTAMP": "fixture", "TAUBENCH_MODE": "standard", "TAUBENCH_USER_MODEL": args.user_model,
             "TAUBENCH_USER_PROVIDER": args.user_provider or "",
             "TAUBENCH_USER_REASONING_EFFORT": args.user_reasoning_effort or ""},
        capture_output=True, text=True, check=True)
    forwarded = wrapper.stdout.splitlines()
    for option, value in (("--user-provider", args.user_provider), ("--user-reasoning-effort", args.user_reasoning_effort)):
        if value:
            assert forwarded[forwarded.index(option) + 1] == value
        else:
            assert option not in forwarded
    if anchor:
        python = root / ".venv-taubench/bin/python"
        if not python.is_file():
            pytest.skip("C2(c) INCONCLUSIVE: repository .venv-taubench/bin/python missing; rerun with LiteLLM 1.82.6 before CLOSE")
        code = '''
import importlib.metadata, json, sys
from unittest.mock import patch
with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")), patch("socket.socket.connect_ex", side_effect=AssertionError("network forbidden")):
    import litellm
    from litellm.llms.openrouter.chat.transformation import OpenrouterConfig
    assert importlib.metadata.version("litellm") == "1.82.6", "C2(c) requires LiteLLM 1.82.6"
    params = json.load(sys.stdin)
    params.pop("timeout")
    params.pop("num_retries")
    litellm.drop_params = True
    optional = litellm.get_optional_params(model="openai/gpt-oss-120b", custom_llm_provider="openrouter", **params)
    body = OpenrouterConfig().transform_request(model="openai/gpt-oss-120b", messages=[{"role": "user", "content": "fixture"}], optional_params=optional, litellm_params={}, headers={})
    print(json.dumps(body))
'''
        transformed = subprocess.run([str(python), "-B", "-c", code], input=json.dumps(user),
            env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1", "LITELLM_LOCAL_MODEL_COST_MAP": "true"},
            cwd=tmp_path, capture_output=True, text=True, timeout=30)
        assert transformed.returncode == 0, transformed.stderr
        body = json.loads(transformed.stdout)
        assert body["provider"] == extra["provider"]
        assert body["reasoning"] == extra["reasoning"]
        assert "extra_body" not in body


def _main_contract(monkeypatch, tmp_path, scenario):
    """Capture subprocess arguments, write sequence, byte content, logs and exit behavior."""
    bench = tmp_path / "data/tau2-bench"
    _inputs(bench)
    # Supply a complete synthetic environment; never consult real credentials or endpoints.
    monkeypatch.setattr(runner.os, "environ", {
        "MODEL_TEST_BASE": str(tmp_path), "EVAL_TIMESTAMP": "session",
        "TAUBENCH_USER_API_KEY": "synthetic-user-key", "OPENAI_API_KEY": "synthetic-key",
    })
    monkeypatch.setattr(runner, "datetime", SimpleNamespace(
        now=lambda: SimpleNamespace(isoformat=lambda: "2000-01-02T03:04:05")
    ))
    monkeypatch.setattr(runner, "_package_version", lambda name: "fixed-" + name)
    monkeypatch.setattr(runner, "_unsupported_sampling_params", lambda: ["seed", "temperature"])
    calls, writes = [], []
    writer = runner.write_json_atomic

    def write(path, value):
        if scenario == "redaction_failure" and path.name == "results.json":
            raise OSError("synthetic redaction failure")
        writer(path, value)
        writes.append([path.relative_to(tmp_path).as_posix(), path.read_text(encoding="utf-8")])

    monkeypatch.setattr(runner, "write_json_atomic", write)

    def check_output(command, *, text):
        calls.append(["git", command, text])
        return "wrong-commit" if scenario == "commit_failure" else runner.SOURCE_COMMIT + "\n"

    def run(command, *, cwd, env, check):
        calls.append(["run", command, str(cwd), env, check])
        upstream = Path(command[command.index("--save-to") + 1])
        upstream.mkdir(parents=True)
        (upstream / "results.json").write_text(json.dumps({
            "messages": [{"api_key": "synthetic-secret", "content": "응답"}],
        }), encoding="utf-8")
        if scenario not in ("missing_shim", "upstream_failure"):
            Path(env["TAUBENCH_REMOVED_PARAMS_OUT"]).write_text(json.dumps({
                "removed_params": ["seed"], "adjusted_params": ["max_tokens"],
                "user_removed_params": ["temperature"],
                "request_counts": {"matched": 0 if scenario == "unmatched_shim" else 1},
            }), encoding="utf-8")
        if scenario == "upstream_failure":
            raise runner.subprocess.CalledProcessError(7, command)
        if scenario == "interrupt":
            raise KeyboardInterrupt()

    monkeypatch.setattr(runner.subprocess, "check_output", check_output)
    monkeypatch.setattr(runner.subprocess, "run", run)
    args = ["--model", "candidate", "--domain", "retail", "--split", "test",
            "--base-url", "http://unused.invalid/v1/chat/completions"]
    if scenario in ("standard_local", "standard_external", "standard_explicit"):
        args += ["--mode", "standard", "--user-model",
                 "openrouter/user" if scenario == "standard_external" else "local-user"]
        if scenario == "standard_explicit":
            args += ["--user-base-url", "http://other.invalid/v1/chat/completions"]
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            rc = runner.main(args)
        except KeyboardInterrupt:
            rc = "KeyboardInterrupt"
    assert rc == ("KeyboardInterrupt" if scenario == "interrupt" else
                  2 if scenario in ("commit_failure", "upstream_failure", "redaction_failure") else 0)
    assert sum(call[0] == "run" for call in calls) == (0 if scenario == "commit_failure" else 1)
    files = {p.relative_to(tmp_path).as_posix(): p.read_bytes().decode("utf-8")
             for p in sorted((tmp_path / "results").rglob("*.json"))}
    value = {"rc": rc, "calls": calls, "writes": writes, "files": files,
             "stdout": stdout.getvalue(), "stderr": stderr.getvalue(),
             "environ": dict(runner.os.environ)}
    serialized = json.dumps(value, ensure_ascii=False)
    for original, replacement in ((str(tmp_path), "<ROOT>"), (runner.sys.executable, "<PYTHON>"),
                                  (str(Path(runner.__file__).resolve().parent), "<RUNNER>"),
                                  (str(Path(runner.__file__).resolve().parents[3]), "<CODE_ROOT>")):
        serialized = serialized.replace(original, replacement)
    return hashlib.sha256(serialized.encode()).hexdigest()


# Captured with fixed subprocess/time fixtures; R6 adds only child PYTHONPATH.
# Normalize its checkout root so the contract hash stays portable across machines.
@pytest.mark.parametrize("scenario,expected", [
    ("success", "48fcd2e3532417776022341ac80ec7243178024bc21203c08dbaea7dea30b765"),
    ("standard_local", "511c37a02fb0ac8fe8d68b589cbc46effd1022a26d9bc6db694e160fa011ce36"),
    ("standard_external", "b64e7ebcfacc4336e4aec601d0673ecfff5a0fe25e544fd9cae53534e6c48c38"),
    ("standard_explicit", "05827d612b65ae0a5abc7122fdecfaee2ab80ff462ab29f154cec04f728fb5cd"),
    ("missing_shim", "2c1ae3e20739be7dbffbd891f0892abdf74bb80472db6fedfc66f82867523ac9"),
    ("unmatched_shim", "3464656a4c50fce879d285b8af9a81af810a041289fe34e4b83e230a03c75c8b"),
    ("upstream_failure", "21bbc4bf6d3c0b7a322a00c0a4d5dc054337e372b5cd64c924da987abe1ae77b"),
    ("redaction_failure", "3cb01f23cce8675262d0be08230e99b45b50fe525729289c976ef5d1cf04d279"),
    ("commit_failure", "81f3256ad4904e036600dface889e3b31d4baad536ae0cf7519a959cacd2e76d"),
    ("interrupt", "7105777c0936c28bdbf8cfd8238c6f2579c5b5ed5d9eaa3f66021e3b993884ed"),
])
def test_main_subprocess_storage_stdout_and_rc_contract(monkeypatch, tmp_path, scenario, expected):
    assert _main_contract(monkeypatch, tmp_path, scenario) == expected
