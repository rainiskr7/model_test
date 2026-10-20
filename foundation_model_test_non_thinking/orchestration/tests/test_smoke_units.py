"""Transport-free smoke checks; the separate shell test owns HTTP integration."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from orchestration.smoke import artifacts, execution, memory_transport
from orchestration.smoke.cleanup import remove_base
from orchestration.smoke.configuration import Context, read_key
from orchestration.smoke.isolation import environment, outside
from orchestration.smoke.offline_checks import fixture

ROOT = Path(__file__).resolve().parents[2]


def test_real_runners_memory_transport(tmp_path):
    # Isolate third-party import-time HF cache settings from pytest collection.
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([str(ROOT / ".venv/bin/python"), "-B", "-m",
                           "orchestration.smoke.memory_transport", "--out", str(tmp_path / "memory-summary.json")],
                          cwd=tmp_path, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    reports = json.loads(Path(proc.stdout.splitlines()[-1]).read_text())
    (tmp_path / "memory-summary.json").write_text(json.dumps(reports, indent=2))
    assert len(reports) == 13


def test_timeout_blocks_later_tracks(monkeypatch, tmp_path):
    ctx = Context(ROOT, tmp_path, {}, "timeout", "fixture", "http://unused", tmp_path)
    calls = []
    def fail(ctx, track):
        calls.append(track)
        result = execution.record(ctx, track)
        result.update(status="FAIL", timeout=True)
        return result
    monkeypatch.setattr(execution, "execute", fail)
    result = execution.run(ctx, ["functionchat", "taubench", "multimodal"])
    assert calls == ["functionchat"]
    assert [r["status"] for r in result["tracks"]] == ["FAIL", "INCONCLUSIVE", "INCONCLUSIVE"]
    assert result["rc"] == 1


@pytest.mark.parametrize("statuses,rc", [(["PASS"], 0), (["INCONCLUSIVE"], 77),
    (["FAIL", "INCONCLUSIVE"], 1), (["INCONCLUSIVE", "FAIL"], 1)])
def test_aggregation(statuses, rc):
    assert execution.aggregate([{"status": s} for s in statuses]) == rc


def test_environment_cleans_external_keys_and_caches(monkeypatch, tmp_path):
    monkeypatch.setenv("TAUBENCH_USER_API_KEY", "must-not-leak")
    monkeypatch.setenv("HF_DATASETS_CACHE", "/original/cache")
    monkeypatch.setenv("HTTP_PROXY", "http://external")
    env = environment(ROOT, tmp_path, "fixture")
    assert "TAUBENCH_USER_API_KEY" not in env and "HTTP_PROXY" not in env
    assert env["HF_DATASETS_CACHE"].startswith(str(tmp_path))
    assert env["PYTHONDONTWRITEBYTECODE"] == env["HF_HUB_OFFLINE"] == "1"
    with pytest.raises(ValueError):
        outside(ROOT / "logs/summary.json", ROOT)


def test_dotenv_is_literal(tmp_path):
    path = tmp_path / ".env"
    path.write_text("unrelated line\nKEY='$(touch forbidden); secret'\n")
    assert read_key(path, "KEY") == "$(touch forbidden); secret"


def context(tmp_path):
    return Context(ROOT, tmp_path, {"OPENAI_API_KEY": "synthetic"}, "test", "fixture",
                   "http://127.0.0.1:1/v1", tmp_path)


def write(directory, name, value):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(value))


@pytest.mark.parametrize("dataset", ["singlecall", "call_decision", "dialog"])
def test_functionchat_rc_zero_does_not_hide_item_error(tmp_path, dataset):
    ctx = context(tmp_path)
    directory = artifacts.result_dir(ctx, "language/functionchat")
    for name in ("singlecall", "call_decision", "dialog"):
        raw = dict(metadata={"subset_limit": 1}, results=[dict(
            error=None, raw_response={"model": "fixture"}, model_output={"content": "A"})])
        if name == dataset:
            raw["results"][0]["error"] = "request failed"
        write(directory, name + ".json", raw)
    write(directory, "coverage.json", {"source": {}, "datasets": {}, "not_measured": {}})
    with pytest.raises(ValueError, match="item error"):
        artifacts.functionchat(ctx, 0)


@pytest.mark.parametrize("mutation", ["none", "extra_failure", "runner_rc", "unresolved", "empty"])
def test_multimodal_only_count_shortfall_allowed(tmp_path, mutation):
    ctx = context(tmp_path)
    directory = artifacts.result_dir(ctx, "vision/multimodal/k_dtcbench")
    counts = dict(attempted=1, measured=1, errored=0, unresolved=0)
    status = dict(publishable=False, failures=["기대 건수 240와 다름"])
    if mutation == "extra_failure":
        status["failures"].append("another failure")
    if mutation == "unresolved":
        counts["unresolved"] = 1
    write(directory, "results.json", [{"response": "" if mutation == "empty" else "A",
                                      "predicted": "A", "error": None}])
    write(directory, "summary.json", dict(model="fixture", total=1, counts=counts,
          publish_status=status, run_config={"extra": {"limit": 1}}))
    write(directory / "_derived", "publish.json", dict(counts=counts, **status))
    if mutation == "none":
        assert len(artifacts.multimodal(ctx, 1)) == 3
    else:
        with pytest.raises(ValueError):
            artifacts.multimodal(ctx, 0 if mutation == "runner_rc" else 1)


def test_raw_timeout_detected_even_with_rc_zero(monkeypatch, tmp_path):
    ctx = context(tmp_path)
    (tmp_path / "logs/smoke/test").mkdir(parents=True)
    directory = artifacts.result_dir(ctx, "language/functionchat")
    write(directory, "singlecall.json", {"results": [{"error": "TimeoutError: task timeout"}]})
    child = SimpleNamespace(returncode=0, communicate=lambda **kw: ("", None))
    monkeypatch.setattr(execution.subprocess, "Popen", lambda *a, **kw: child)
    result = execution.record(ctx, "functionchat")
    with pytest.raises(ValueError, match="runner timeout"):
        execution.invoke(ctx, "functionchat", ["unused"], result)
    assert result["timeout"] and result["runner_rc"] == 0


def test_cli_outside_cwd_missing_template_is_inconclusive(monkeypatch, tmp_path):
    with fixture(ROOT, "127.0.0.1:1") as root:
        monkeypatch.setenv("SMOKE_FIXTURE_HOST", "127.0.0.1:1")
        (root / "tokenizer/chat_template.jinja").unlink()
        shutil.copytree(ROOT / "orchestration/smoke", root / "orchestration/smoke")
        output = tmp_path / "summary.json"
        script = root / "orchestration/smoke/run_smoke.sh"
        proc = subprocess.run(["bash", str(script), "fixture", "harness", "--out", str(output)],
                              cwd=tmp_path, capture_output=True, text=True)
        assert proc.returncode == 77, proc.stderr
        summary = json.loads(proc.stdout)
        base = Path(summary["base"])
        try:
            assert summary == json.loads(output.read_text())
            assert summary["tracks"][0]["status"] == "INCONCLUSIVE"
            assert "synthetic-smoke-key" not in proc.stdout + proc.stderr
            assert (base / "logs/smoke" / summary["timestamp"] / "harness.json").is_file()
            assert not (base / ".env").exists()
        finally:
            remove_base(base, root, created=base)


@pytest.mark.parametrize("args", [["qwen35fp8.conf"], ["qwen35fp8", "unknown"]])
def test_invalid_cli(args, tmp_path):
    proc = subprocess.run(["bash", str(ROOT / "orchestration/smoke/run_smoke.sh"), *args],
                          cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 2
