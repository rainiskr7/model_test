"""Synthetic unit fixtures and pre-extraction subprocess/storage contracts."""

import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

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
    }
    assert original == {"OPENAI_API_KEY": "synthetic", "TAU2_DATA_DIR": "old"}


@pytest.mark.parametrize("domain", ["telecom", "retail"])
def test_split_summary_preserves_existing_telecom_label(domain):
    args = SimpleNamespace(domain=domain, split="test")
    assert runner._split_summary(args, ["one"], {
        "task_count": 2, "not_measured_task_count": 1,
    }) == "[taubench] telecom split 'test': 1/2 judge-free tasks; 1 not measured"


@pytest.mark.parametrize("external", [False, True])
def test_prepare_llm_args_keeps_user_protocol_independent(monkeypatch, external):
    monkeypatch.setattr(runner, "_unsupported_sampling_params", lambda: ["temperature"])
    args = runner.parse_args([
        "--model", "candidate", "--mode", "standard", "--user-model",
        "openrouter/user" if external else "local-user",
        "--request-timeout", "3", "--max-tokens", "17",
    ])
    environ = {"TAUBENCH_USER_API_KEY": "synthetic"}
    candidate, user, removed = runner._prepare_llm_args(args, "http://unused/v1", environ)
    assert candidate == {"api_base": "http://unused/v1", "timeout": 3.0,
                         "num_retries": 0, "max_tokens": 17}
    assert user == ({"timeout": 120.0, "num_retries": 0, "max_tokens": 16384, "temperature": 0.0}
                    if external else {"api_base": "http://unused/v1", "timeout": 120.0,
                                      "num_retries": 0, "max_tokens": 16384})
    assert removed == ([] if external else ["temperature"])
    assert environ == ({"TAUBENCH_USER_API_KEY": "synthetic", "OPENROUTER_API_KEY": "synthetic"}
                       if external else {"TAUBENCH_USER_API_KEY": "synthetic"})


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
                                  (str(Path(runner.__file__).resolve().parent), "<RUNNER>")):
        serialized = serialized.replace(original, replacement)
    return hashlib.sha256(serialized.encode()).hexdigest()


# Captured from the original main, with subprocess and time replaced by fixed fixtures.
@pytest.mark.parametrize("scenario,expected", [
    ("success", "f9a2b10055108fa63a70ceec3d1883756d50d5c13ca8ec255d981fa155860281"),
    ("standard_local", "5975763b4a2df59d05f411a4f84804c99440cb2afa0688d99c07f0578a18e50f"),
    ("standard_external", "b34bd1a9687be48e2affb6b3f60a72086530d311703add26fd0c2d8a4530deec"),
    ("standard_explicit", "bc36561feda6578ec73e25ceeea0e96a418ce07470dc6a11f92ca3aeeb8e6b67"),
    ("missing_shim", "fe04e3a02f6522ba580b8f14f76b6cdd0c13f387e2547c713ee88bf36a576afa"),
    ("unmatched_shim", "67b14bb435aa3562eb2083a02baa6aaa8000369ebd20e21fdcaadeea1c2a49c8"),
    ("upstream_failure", "4fdabcc54717ffa93d20ca88defd4a22c9c10894b2bde6722839e54fdd450aa6"),
    ("redaction_failure", "c6b327210027d8dfe2c7fd79af425a98c0a45d01f13f9dcc878e31a57f827a36"),
    ("commit_failure", "81f3256ad4904e036600dface889e3b31d4baad536ae0cf7519a959cacd2e76d"),
    ("interrupt", "49a9ef7d0b38203a71869fe1a3a31eb06bdb400d1f617666d6f8c5a3d3c9a111"),
])
def test_main_subprocess_storage_stdout_and_rc_contract(monkeypatch, tmp_path, scenario, expected):
    assert _main_contract(monkeypatch, tmp_path, scenario) == expected
