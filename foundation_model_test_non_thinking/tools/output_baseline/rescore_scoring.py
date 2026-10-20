"""Rescore private output copies, never the shared input snapshot."""

import shutil


def run(runner, entries):
    for item in entries:
        kind, relative = item["kind"], item["path"]
        if kind not in {"taubench", "functionchat"}:
            continue
        target = runner.output / "rescore" / relative
        shutil.copytree(runner.snapshot / relative, target)
        # A successful command must produce a fresh summary, not reuse the input.
        (target / "summary.json").unlink(missing_ok=True)
        name = kind + "/" + relative + "/summary.json"
        record = runner.run(name, ["-m", f"shared.{kind}.scoring.score_run",
                                  "--results-dir", str(target)], (0, 1))
        runner.artifact(name, target / "summary.json", record["rc"])
