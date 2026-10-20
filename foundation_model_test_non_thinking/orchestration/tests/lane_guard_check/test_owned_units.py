"""Refuse real process activity when ownership evidence is unavailable."""

import unittest
from unittest.mock import patch

from orchestration.tests.lane_guard_check.owned import current_record, ps_field
from orchestration.tests.lane_guard_check.real_cases import real_case
from orchestration.tests.lane_guard_check.report import Inconclusive


class OwnedTests(unittest.TestCase):
    def test_reused_pid_is_rejected_before_command_lookup(self):
        with patch("orchestration.tests.lane_guard_check.owned.ps_field", return_value="new start") as ps:
            self.assertIsNone(current_record("42", {"stamp": "old start"}))
            ps.assert_called_once_with("42", "lstart")

    def test_permission_denial_is_inconclusive_without_launch(self):
        with patch("subprocess.run", side_effect=PermissionError("denied")):
            with self.assertRaises(Inconclusive):
                ps_field(42, "stat")
            with patch("subprocess.Popen") as launch:
                with self.assertRaises(Inconclusive):
                    real_case(None, None, None, None, "denied")
                launch.assert_not_called()
