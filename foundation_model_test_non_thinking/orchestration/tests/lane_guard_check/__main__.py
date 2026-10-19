"""Run the bounded-process suite and retain reproducible artifacts."""

from pathlib import Path
import sys
import tempfile
import unittest

from orchestration.tests.lane_guard_check.contract_cases import invalid_rows_case, same_track_case, same_track_real_case
from orchestration.tests.lane_guard_check.fixture import head_guard
from orchestration.tests.lane_guard_check.model_cases import (
    duplicate_case, health_case, heat_case, manual_case, overlap_case,
)
from orchestration.tests.lane_guard_check.path_cases import (
    default_conf_case, path_case, regression_case, unsupported_case,
)
from orchestration.tests.lane_guard_check.real_cases import real_case
from orchestration.tests.lane_guard_check.report import Report


def unit_cases(report):
    names = ["adapter", "model_cases", "owned", "report"]
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        f"orchestration.tests.lane_guard_check.test_{name}_units" for name in names])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    report.check("unit checks", result.wasSuccessful(), f"tests={result.testsRun}")


def main():
    repo = Path(__file__).resolve().parents[3]
    if len(sys.argv) > 2:
        print("usage: test_lane_guard_isolated.sh [guard-script]", file=sys.stderr)
        return 2
    target = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else repo / "orchestration/lane_guard.sh"
    root = Path(tempfile.mkdtemp(prefix="lane_guard_check.", dir="/tmp"))
    print(f"ARTIFACTS={root}", flush=True)
    report = Report()
    old = head_guard(repo, root)
    report.run("units", lambda: unit_cases(report))
    report.run("regression", lambda: regression_case(repo, root, target, old, report))
    for case in (path_case, unsupported_case, default_conf_case, health_case,
                 duplicate_case, manual_case, overlap_case, same_track_case, same_track_real_case, invalid_rows_case):
        report.run(case.__name__, lambda case=case: case(repo, root, target, report))
    for hot, label in (("84 70", "gpu"), ("60 96", "sensor")):
        report.run(label, lambda hot=hot, label=label: heat_case(repo, root, target, report, hot, label))
    report.run("real_before", lambda: real_case(repo, root, old, report, "real_before", decoy=False))
    report.run("real_logical", lambda: real_case(repo, root, target, report, "real_logical", physical=False))
    report.run("real_physical", lambda: real_case(repo, root, target, report, "real_physical"))
    return report.finish(root / "summary.json")


if __name__ == "__main__":
    sys.exit(main())
