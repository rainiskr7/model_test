"""Run the five real report entry points against the live results tree."""

from pathlib import Path

REPORTS = ("report_agent_tracks", "report_harness_tracks", "report_multimodal_tracks",
           "report_nlu_tracks", "report_taubench_tracks")


def run(runner, entries):
    for module in REPORTS:
        name = "reports/" + module + ".stdout"
        record = runner.run(name, ["-m", "reports." + module, "--base", str(runner.base)])
        runner.artifact(name, Path(record["stdout_path"]), record["rc"])
