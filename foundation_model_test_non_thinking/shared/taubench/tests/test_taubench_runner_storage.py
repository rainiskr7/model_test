"""Exercise manifest writes and finally-path redaction without upstream execution."""

import json
from pathlib import Path

import pytest

from shared.taubench.runner import run_taubench as runner
from shared.jsonwrite.atomic_json import write_json_atomic


def assert_json_bytes(path):
    raw = path.read_bytes()
    value = json.loads(raw)
    assert raw == (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return value


@pytest.mark.parametrize("upstream_fails", [False, True], ids=["success", "failure"])
def test_main_saves_manifest_and_redacts_even_on_failure(monkeypatch, tmp_path, capsys, upstream_fails):
    bench = tmp_path / "data/tau2-bench"
    domain = bench / "data/tau2/domains/telecom"
    domain.mkdir(parents=True)
    (domain / "tasks.json").write_text(json.dumps([{
        "id": "synthetic-task", "evaluation_criteria": {"reward_basis": ["DB"]},
    }]), encoding="utf-8")
    (domain / "split_tasks.json").write_text(
        json.dumps({"test": ["synthetic-task"]}), encoding="utf-8",
    )
    monkeypatch.setenv("MODEL_TEST_BASE", str(tmp_path))
    monkeypatch.setenv("EVAL_TIMESTAMP", "session")
    monkeypatch.setenv("SERVING_UNSUPPORTED_SAMPLING_PARAMS", "")
    output = tmp_path / "results/test_model/session/language/taubench"
    manifest_path = output / "run_manifest.json"
    initial = []
    calls = []
    secret = "synthetic-credential-for-storage-test"

    def fake_check_output(command, *, text):
        assert command == ["git", "-C", str(bench), "rev-parse", "HEAD"]
        assert text is True
        return runner.SOURCE_COMMIT + "\n"

    def fake_run(command, *, cwd, env, check):
        calls.append(command)
        assert cwd == bench and check is True
        assert env["TAU2_DATA_DIR"] == str(bench / "data")
        initial_manifest = assert_json_bytes(manifest_path)
        assert initial_manifest["status"] == "running"
        assert initial_manifest["split"]["task_ids"] == ["synthetic-task"]
        initial.append(manifest_path.read_bytes())
        upstream = Path(command[command.index("--save-to") + 1])
        assert upstream == output / "upstream/telecom"
        payload = {
            "info": {"agent_info": {"llm_args": {"api_key": secret}}},
            "messages": [{"api_key": secret, "content": "보존할 응답"}],
        }
        for relative in ("results.json", "nested/request.json"):
            path = upstream / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
        if upstream_fails:
            raise runner.subprocess.CalledProcessError(7, command)
        return runner.subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runner.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.write_json_atomic is write_json_atomic
    rc = runner.main([
        "--model", "test/model", "--base-url", "http://unused.invalid/v1",
        "--mode", "solo", "--split", "test",
    ])
    assert len(calls) == 1
    assert rc == (2 if upstream_fails else 0)
    manifest = assert_json_bytes(manifest_path)
    assert manifest["status"] == ("running" if upstream_fails else "completed")
    if upstream_fails:
        assert manifest_path.read_bytes() == initial[0]
        assert "completed_at" not in manifest
        assert "upstream_results" not in manifest
    else:
        assert manifest["completed_at"]
        assert manifest["upstream_results"] == "upstream/telecom/results.json"
        assert manifest_path.read_bytes() != initial[0]
    for relative in ("results.json", "nested/request.json"):
        path = output / "upstream/telecom" / relative
        value = assert_json_bytes(path)
        assert secret.encode() not in path.read_bytes()
        assert value["info"]["agent_info"]["llm_args"]["api_key"] == "***REDACTED***"
        assert value["messages"] == [{"api_key": "***REDACTED***", "content": "보존할 응답"}]
    assert {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()} == {
        "run_manifest.json", "upstream/telecom/results.json", "upstream/telecom/nested/request.json",
    }
    captured = capsys.readouterr()
    assert "api_key 를 2개 파일에서 제거했다" in captured.out
    if upstream_fails:
        assert "ERROR: CalledProcessError:" in captured.err
    else:
        assert captured.err == ""
