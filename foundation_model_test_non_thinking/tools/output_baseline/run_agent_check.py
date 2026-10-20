"""Compare agent --check stdout in full, including its return code."""

from pathlib import Path


def run(runner, entries):
    for item in entries:
        if item["kind"] != "agent":
            continue
        name = "agent/" + item["path"] + "/stdout"
        record = runner.run(name, ["-m", "shared.agent.scoring.score_run", "--check",
                                  "--results-dir", str(runner.snapshot / item["path"])], (0, 1, 3))
        stdout = Path(record["stdout_path"])
        record["stdout_full"] = stdout.read_text()
        runner.artifact(name, stdout, record["rc"])
