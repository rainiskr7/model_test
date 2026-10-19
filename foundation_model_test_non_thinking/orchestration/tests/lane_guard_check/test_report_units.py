"""Check that unavailable real evidence cannot become overall success."""

from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import tempfile
import unittest

from orchestration.tests.lane_guard_check.report import Report


class ReportTests(unittest.TestCase):
    def test_rc_precedence(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            path = Path(directory) / "summary.json"
            report = Report()
            report.rows = [{"status": "PASS"}]
            self.assertEqual(report.finish(path), 0)
            report.rows.append({"status": "INCONCLUSIVE"})
            self.assertEqual(report.finish(path), 77)
            report.rows.append({"status": "FAIL"})
            self.assertEqual(report.finish(path), 1)
