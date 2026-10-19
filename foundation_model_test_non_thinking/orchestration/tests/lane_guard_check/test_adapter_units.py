"""Pin the fixture adapter contract independently of guard expectations."""

import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

from orchestration.tests.lane_guard_check.adapter import ps_output, select_pids, send_signal


class AdapterTests(unittest.TestCase):
    def test_selection_is_literal_regex_and_parent_scoped(self):
        rows = {"10": {"cmd": "/bin/bash /tmp/a.[x]+/lane.sh", "ppid": 1},
                "11": {"cmd": "sleep 300", "ppid": 10}}
        self.assertEqual(select_pids(rows, "-f", r"^/bin/bash /tmp/a\.\[x\]\+/lane\.sh$"), ["10"])
        self.assertEqual(select_pids(rows, "-P", "10"), ["11"])
        self.assertEqual(select_pids(rows, "-P", "999"), [])

    def test_ps_never_falls_back_to_system_lookup(self):
        rows = {"10": {"cmd": "owned", "stamp": "stamp", "stat": "T"}}
        self.assertEqual(ps_output(rows, ["-axo", "command="]), "owned")
        self.assertEqual(ps_output(rows, ["-p", "999", "-o", "stat="]), "")
        with patch.dict("os.environ", {"LG_CHECK_GUARD_PID": "20"}):
            self.assertEqual(ps_output(rows, ["-p", "20", "-o", "pid="]), "20")
            self.assertEqual(ps_output(rows, ["-p", "999", "-o", "pid="]), "")
        with self.assertRaises(ValueError):
            ps_output(rows, ["aux"])

    def test_real_signal_requires_owned_pid_and_unchanged_identity(self):
        with tempfile.TemporaryDirectory() as directory, patch("os.kill") as kill:
            base = Path(directory)
            self.assertEqual(send_signal(base, {"processes": {}}, {}, ["-STOP", "999"], True), 1)
            rows = {"42": {"stamp": "old"}}
            with patch("orchestration.tests.lane_guard_check.adapter.current_record", return_value=None):
                self.assertEqual(send_signal(base, {"processes": rows}, rows, ["-CONT", "42"], True), 1)
            kill.assert_not_called()
