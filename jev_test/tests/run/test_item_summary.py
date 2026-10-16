"""무엇: 항목 요약 CLI 통합 · 입력: tmp_path 합성 데이터·설정·분할 · 출력: JSONL·실패 · 계약 §6-2."""

import json
from pathlib import Path
import subprocess
import sys

import yaml

from tests.run.t0_support import add_datasets

from jeveval.data.grouping import group_rows
from jeveval.data.split import build_split_plan
from jeveval.io.config import read_yaml
from jeveval.io.splits import write_split_plan
from jeveval.types import PoolResult, SourceRow


REPO = Path(__file__).resolve().parents[2]
BOOTSTRAP = "import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); runpy.run_module('jeveval.run.item_summary',run_name='__main__')"


def _prepare(root):
    add_datasets(root)
    tasks = root / "tasks"
    (tasks / "lists").mkdir(parents=True)
    task = read_yaml(REPO / "configs/tasks/fc_call_decision.yaml")
    (tasks / "fc.yaml").write_text(yaml.safe_dump(task))
    (tasks / "b1.yaml").write_text("not a task")
    for name in ("fc_actions", "functionchat_none", "functionchat_normalization"):
        (tasks / f"lists/{name}.json").write_bytes((REPO / f"configs/tasks/lists/{name}.json").read_bytes())
    data = [dict(serial_num=i, input_messages=[dict(role="system", content="PRIVATE_SYSTEM"),
            dict(role="user", content="PRIVATE_USER")], input_tools=[dict(function=dict(
            name="synthetic_tool", description="PRIVATE_DESCRIPTION"))],
            type_of_output="call" if i == 1 else "slot", ground_truth={"tool_calls": [
            {"function": {"name": "synthetic_tool"}}]} if i == 1 else {}) for i in (1, 2)]
    (root / "data.jsonl").write_text("\n".join(json.dumps(r) for r in data))
    cfg = dict(source={"file": "data.jsonl"}, group_key="fc_components", pool={"kind": "all"}, extra=True)
    (root / "rules.yaml").write_text(yaml.safe_dump({"sets": {task["set"]: cfg}}))
    rows = [SourceRow(task["set"], str(r["serial_num"]), r) for r in data]
    groups = group_rows(rows, task["group_key"])
    plan = build_split_plan(rows, groups, PoolResult(["1"], {"all": 1}), task["set"], cfg, 1, 1)
    write_split_plan(plan, root / "splits/fc_call_decision.json")
    return plan


def _run(root, task="all"):
    return subprocess.run([sys.executable, "-I", "-c", BOOTSTRAP, str(REPO),
        "--root", str(root), "--rules", "rules.yaml", "--tasks", "tasks", "--splits", "splits",
        "--task", task], text=True, capture_output=True, cwd=root)


def test_synthetic_cli_all_stages_and_no_source_leak(tmp_path):
    plan = _prepare(tmp_path)
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.splitlines()) == 1 and "PRIVATE_" not in result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["task"] == "fc"
    stages = summary["by_stage"]
    assert {s: v["n"] for s, v in stages.items()} == dict(dev=1, test=0, extra=1)
    assert stages["test"] == dict(n=0, questions={}, flags={}, stratum=None, baseline=0)
    for stage in ("dev", "extra"):
        assert stages[stage]["questions"]["tool"]["n_options"] == 2
        assert sum(stages[stage]["questions"]["tool"]["gold"].values()) == 1
    assert _run(tmp_path, "fc.yaml").stdout == result.stdout
    assert _run(tmp_path, "unknown").returncode != 0
    path = tmp_path / "splits/fc_call_decision.json"
    data = plan.to_dict()
    data["test"] = data["dev"]
    path.write_text(json.dumps(data))
    bad = _run(tmp_path)
    assert bad.returncode != 0 and bad.stdout == "" and "PRIVATE_" not in bad.stderr
