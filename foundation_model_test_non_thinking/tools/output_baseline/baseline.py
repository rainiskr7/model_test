"""HEAD versus working tree, with one shared input snapshot."""

import argparse
import json
import tempfile
import time
from pathlib import Path

from tools.output_baseline import boundary, prerequisite
from tools.output_baseline import derive_multimodal, render_reports, rescore_scoring, run_agent_check
from tools.output_baseline.compare import compare, expected_outputs
from tools.output_baseline.execution import Runner
from tools.output_baseline.inputs import load_inputs, sha256, validate_snapshot
from tools.output_baseline.snapshot import archive_code, copy_inputs, dirty_state


def prepare(base, selected, evidence, manifest):
    entries = load_inputs(selected)
    manifest.update(inputs_file=str(selected), inputs_file_sha256=sha256(selected), inputs=entries,
                    interpreter=str(base / ".venv/bin/python"), expected_outputs=expected_outputs(entries))
    manifest["snapshot"] = copy_inputs(base, evidence / "inputs", entries)
    metrics = base / "data/Ko-AgentBench/bench/runner/metrics.py"
    manifest["external_metrics"] = {"path": str(metrics), "sha256": sha256(metrics), "MODEL_TEST_BASE": str(base)}
    manifest["code"] = archive_code(base, evidence / "head", evidence)
    manifest["code"]["dirty"] = dirty_state(base, evidence)
    manifest["prerequisite"] = prerequisite.run(base, evidence)
    if not manifest["prerequisite"]["ok"]:
        raise RuntimeError("runner_requests prerequisite failed")
    return entries


def run_sides(base, evidence, entries, manifest):
    snapshot = Path(manifest["snapshot"]["root"])
    for side, code in (("head", evidence / "head"), ("working", base)):
        runner = Runner(base, code, snapshot, evidence / "outputs" / side, base / ".venv/bin/python")
        manifest["sides"][side] = runner.record
        for stage in (run_agent_check, rescore_scoring, render_reports, derive_multimodal):
            print(f"{side}: {stage.__name__}", flush=True)
            problems = validate_snapshot(manifest["snapshot"])
            if problems:
                raise RuntimeError("; ".join(problems))
            try:
                stage.run(runner, entries)
            except Exception as exc:
                runner.record["errors"].append(f"{stage.__name__}: {type(exc).__name__}: {exc}")


def execute(base, selected, out):
    started = time.monotonic()
    evidence = Path(tempfile.mkdtemp(prefix="output-baseline-"))
    manifest = {"version": 1, "evidence_root": str(evidence), "errors": [], "sides": {},
                "reports_read_live_results": True, "harness_report_may_change_with_running_lanes": True,
                "report_input_root": str(base), "reports_are_snapshotted": False}
    print(f"evidence_root={evidence}", flush=True)
    manifest["boundary"] = boundary.start(base, evidence)
    try:
        entries = prepare(base, selected, evidence, manifest)
        run_sides(base, evidence, entries, manifest)
        metrics = manifest["external_metrics"]
        metrics["sha256_after"] = sha256(metrics["path"])
        if metrics["sha256_after"] != metrics["sha256"]:
            raise RuntimeError("external metrics.py changed during execution")
    except Exception as exc:
        manifest["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        try:
            boundary.finish(base, manifest["boundary"])
        except Exception as exc:
            manifest["boundary"]["ok"] = False
            manifest["errors"].append(f"boundary: {type(exc).__name__}: {exc}")
    if manifest["errors"]:
        rc, messages = 2, manifest["errors"]
    else:
        rc, messages = compare(manifest)
    manifest.update(rc=rc, comparison=messages, elapsed_seconds=time.monotonic() - started)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (evidence / "manifest.json").write_bytes(out.read_bytes())
    print("\n".join(messages))
    print(f"rc={rc} elapsed_seconds={manifest['elapsed_seconds']:.3f} manifest={out}")
    return rc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=Path(__file__).with_name("inputs.txt"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    base = Path(__file__).resolve().parents[2]
    try:
        return execute(base, args.inputs.resolve(), boundary.safe_output(base, args.out))
    except Exception as exc:
        print(f"baseline failed: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
