"""무엇: status/dry-run 무전송·무쓰기. 입력: 합성 split/기록. 출력: 트리 바이트와 mtime 동일."""

from dataclasses import replace
from pathlib import Path
import sys
import shlex

import pytest
import yaml

from jeveval.io.splits import write_split_plan
from jeveval.types import SplitPlan


def snapshot(root):
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file() and not p.is_symlink() and "jeveval" not in p.parts}


def test_all_dry_runs_do_not_call_python_curl_or_write(sandbox):
    # Read-only Python metadata helpers are allowed; evaluation CLI and curl are not.
    before = snapshot(sandbox.root)
    for script, args in [
        ("lane", None), ("replay", ["model", "old", "r1", "synthetic reason"]),
        ("compare", ["r1", "model", "b1"]), ("status", ["model", "r1"]), ("stop", ["now", "model"]),
    ]:
        result = sandbox.run(script, args, OPS_DRY_RUN="1", SETS="kosgd")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "DRY" in result.stdout
        if script == "lane":
            assert "--offline" in result.stdout and result.stdout.count("DRY healthy") == 2
    assert snapshot(sandbox.root) == before
    assert not sandbox.calls.exists() and not sandbox.curls.exists()


@pytest.mark.parametrize("model,derived", [("model", True), ("joint", False)])
@pytest.mark.parametrize("script", ["lane", "replay"])
def test_dry_run_uses_model_scoring_without_cli_or_writes(sandbox, model, derived, script):
    before = snapshot(sandbox.root)
    args = ([model, "host", "fallback", "1234", "SYNTHETIC_KEY", "r1"] if script == "lane"
            else [model, "old", "r1", "synthetic reason"])
    result = sandbox.run(script, args, OPS_DRY_RUN="1", SETS="kosgd", SYNTHETIC_KEY="")
    assert result.returncode == 0, result.stdout + result.stderr
    commands = [shlex.split(line) for line in result.stdout.splitlines() if line.startswith("DRY ")]
    actions = [c for c in commands if "configs/tasks/kosgd_actions_only.yaml" in c]
    runs = [c for c in actions if "run" in c]
    copies = [c for c in actions if "replay" in c]
    assert len(runs) == 2
    assert len(copies) == (2 if script == "replay" and not derived else 0)
    for command in runs:
        assert ("--offline" in command) == (script == "replay" or derived)
        assert ("--base-url" in command) == (script == "lane" and not derived)
    assert result.stdout.count("DRY healthy") == (0 if script == "replay" else 2 if derived else 4)
    assert snapshot(sandbox.root) == before
    assert not sandbox.calls.exists() and not sandbox.curls.exists()


@pytest.mark.parametrize("scoring", [None, "unknown", "", ["separate"]])
@pytest.mark.parametrize("script", ["lane", "replay"])
def test_invalid_scoring_rejected_before_dry_run_commands(sandbox, scoring, script):
    path = sandbox.root / "configs/models/model.yaml"
    config = yaml.safe_load(path.read_text())
    if scoring is None:
        del config["question_scoring"]
    else:
        config["question_scoring"] = scoring
    path.write_text(yaml.safe_dump(config))
    before = snapshot(sandbox.root)
    args = None if script == "lane" else ["model", "old", "r1", "synthetic reason"]
    result = sandbox.run(script, args, OPS_DRY_RUN="1", SETS="kosgd")
    assert result.returncode == 2
    assert "ops input check failed" in result.stderr
    assert "--task" not in result.stdout
    assert snapshot(sandbox.root) == before
    assert not sandbox.calls.exists() and not sandbox.curls.exists()


def test_status_observes_empty_records_without_writes(sandbox):
    names = ("klue_mrc_answerable", "korfin_asc", "fc_call_decision", "kmhas", "kote_escalation", "kosgd")
    for name in names:
        plan = SplitPlan(name, 1, {}, {}, {"g": ["i"]}, {"g": f"{name}:g:i"}, ["g"], [], [], [], {})
        write_split_plan(plan, sandbox.root / f"configs/splits/{name}.json")
    before = snapshot(sandbox.root)
    result = sandbox.run("status", ["model", "r1"], JEV_PY=sys.executable)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(result.stdout.splitlines()) == 16  # 7 variants × 2 stages + FC extra + header
    assert "parsed_attempt_lines" in result.stdout and "response_raw" not in result.stdout
    assert snapshot(sandbox.root) == before
    assert not sandbox.curls.exists() and not sandbox.calls.exists()


def test_status_counts_retries_and_final_without_exposing_response(sandbox):
    from jeveval.io import records
    from jeveval.types import FinalRecord
    from tests.types.samples import attempt, call

    names = ("klue_mrc_answerable", "korfin_asc", "fc_call_decision", "kmhas", "kote_escalation", "kosgd")
    for name in names:
        plan = SplitPlan(name, 1, {}, {}, {"g": ["i"]}, {"g": f"{name}:g:i"}, ["g"], [], [], [], {})
        write_split_plan(plan, sandbox.root / f"configs/splits/{name}.json")
    directory = sandbox.root / "results/model/r1/A/kmhas/default/dev"
    directory.mkdir(parents=True)
    secret = "PRIVATE_RESPONSE_CANARY_659"
    first = replace(attempt(), logical_id="kmhas:g:i", call_id="kmhas:g:i",
                    terminal=False, response_raw=secret)
    second = replace(first, attempt=2, terminal=True)
    records.append_record(directory / "attempts.jsonl", first)
    records.append_record(directory / "attempts.jsonl", second)
    records.append_record(directory / "final.jsonl",
                          FinalRecord("kmhas:g:i", "ok", None, False, [],
                                      [replace(call(), call_id="kmhas:g:i", attempts=2)]))
    before = snapshot(sandbox.root)
    result = sandbox.run("status", ["model", "r1"], JEV_PY=sys.executable)
    assert result.returncode == 0
    row = next(line.split("\t") for line in result.stdout.splitlines() if line.startswith("kmhas\tdefault\tdev"))
    assert row[3:9] == ["1", "1", "True", "ok:1", "2", "1"]
    assert secret not in result.stdout + result.stderr
    assert snapshot(sandbox.root) == before and not sandbox.curls.exists()
