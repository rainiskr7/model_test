"""C3 감사: 직접 바이트·파생 출처·허용된 metadata 정규화 경계."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

from jeveval.io import run_files


def copy_run(h):
    old = h.directory.parents[2]
    new = old.with_name("r2")
    shutil.copytree(old, new)
    for path in new.rglob("*.json"):
        path.write_bytes(path.read_bytes().replace(b"r1", b"r2"))
    return old, new, new / h.directory.relative_to(old)


def test_direct_run_bytes_and_isolated_cli(audit_h, audit_module):
    h = audit_h
    h.finish()
    old, new, folder = copy_run(h)
    module = audit_module("c3_compare_runs")
    assert module["audit"](old, new)["ok"]
    script = Path(__file__).resolve().parents[2] / "audits/replay_20261019/c3_compare_runs.py"
    checked = subprocess.run([sys.executable, "-I", str(script), str(old), str(new)],
                             capture_output=True, text=True)
    assert checked.returncode == 0 and json.loads(checked.stdout)["ok"] and not checked.stderr
    (folder / "test/final.jsonl").write_bytes(b"")
    result = module["audit"](old, new)
    assert result["differences"] == ["A/fc_call_decision/default/test/final.jsonl"]


def test_normalization_only_approved_fields(audit_module):
    normalize = audit_module("c3_compare_runs")["normalize"]
    value = dict(run_id="old", threshold_sha256="oldhash", dev_input=dict(sha256="hash", nbytes=10),
                 cost=dict(derived_from="results/m/old/A/kosgd/full"))
    direct = normalize(value, "old", "new")
    derived = normalize(value, "old", "new", derived=True)
    assert "threshold_sha256" not in direct and direct["dev_input"]["sha256"] == "hash"
    assert derived["dev_input"] == {"nbytes": 10}
    assert derived["cost"]["derived_from"] == "results/m/new/A/kosgd/full"
    assert value["run_id"] == "old"


def test_derived_final_run_id_replacement(audit_h, audit_module):
    h = audit_h
    h.finish()
    old, new, folder = copy_run(h)
    for parent, run_id in ((h.directory, "r1"), (folder, "r2")):
        for stage in ("dev", "test", "extra"):
            run_files.write_json(parent / stage / "derived.json", {"derived_from": f"results/m/{run_id}/full"})
            path = parent / stage / "final.jsonl"
            lines = [json.loads(line) for line in path.read_text().splitlines()]
            for row in lines:
                row["derived_from"] = f"results/m/{run_id}/full"
            path.write_text("\n".join(json.dumps(r) for r in lines) + "\n")
    assert audit_module("c3_compare_runs")["audit"](old, new)["ok"]
