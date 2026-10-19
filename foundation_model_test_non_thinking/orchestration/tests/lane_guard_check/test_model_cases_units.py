"""Pin synthetic process records."""

import unittest

from orchestration.tests.lane_guard_check.model_cases import process


class ProcessTests(unittest.TestCase):
    def test_defaults_and_explicit_manual_stop(self):
        row = process("sleep 300")
        self.assertEqual(row, {"cmd": "sleep 300", "ppid": 0, "stat": "S",
                               "stamp": "Mon Oct 19 00:00:00 2026"})
        self.assertEqual(process("child", parent=42, stat="T")["ppid"], 42)
        self.assertEqual(process("child", stat="T")["stat"], "T")
