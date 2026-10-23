"""Input: mocked process inspection/launch; output: ownership assertions without spawning."""

import os
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from orchestration.tests.lane_guard_check.owned import Owned, current_record, ps_field
from orchestration.tests.lane_guard_check.real_cases import real_case
from orchestration.tests.lane_guard_check.report import Inconclusive


class OwnedTests(unittest.TestCase):
    def test_reused_pid_is_rejected_before_command_lookup(self):
        with patch("orchestration.tests.lane_guard_check.owned.ps_field", return_value="new start") as ps:
            self.assertIsNone(current_record("42", {"stamp": "old start"}))
            ps.assert_called_once_with("42", "lstart")
        with patch("orchestration.tests.lane_guard_check.owned.ps_field",
                   side_effect=["old start", "S", "owned command", "1"]):
            self.assertEqual(current_record("42", {"stamp": "old start", "ppid": 99}),
                             {"stamp": "old start", "stat": "S", "cmd": "owned command", "ppid": "1"})

    def test_permission_denial_is_inconclusive_without_launch(self):
        with patch("subprocess.run", side_effect=PermissionError("denied")):
            with self.assertRaises(Inconclusive):
                ps_field(42, "stat")
            with patch("subprocess.Popen") as launch:
                with self.assertRaises(Inconclusive):
                    real_case(None, None, None, None, "denied")
                launch.assert_not_called()

    def test_launch_registers_and_validates_each_tree_before_cleanup(self):
        """Mock launch/ps/kill to verify both tree shapes, argv rejection and cleanup."""
        for subshell, bad_argv in ((False, False), (True, False), (True, True)):
            with self.subTest(subshell=subshell, bad_argv=bad_argv), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                fixture = SimpleNamespace(base=base, table=Mock())
                script = base / "lanes/kmmlu.sh"
                (base / "lane.child").write_text("103\n")
                (base / "lane.subshell").write_text("102\n")
                command = f"/bin/bash {script} sample"
                rows = {101: {"ppid": str(os.getpid()), "cmd": command},
                        102: {"ppid": "101", "cmd": "wrong argv" if bad_argv else command},
                        103: {"ppid": "102" if subshell else "101", "cmd": "sleep 300"}}
                fields = {(str(pid), field): value for pid, row in rows.items()
                          for field, value in {"lstart": "stamp", "stat": "S", "command": row["cmd"],
                                               "ppid": row["ppid"]}.items()}
                proc = Mock(pid=101)
                proc.poll.return_value = None
                owned = Owned(fixture)
                with patch("orchestration.tests.lane_guard_check.owned.ps_field",
                           side_effect=lambda pid, field: fields[(str(pid), field)]), \
                     patch("subprocess.Popen", return_value=proc) as launch, patch("os.kill") as kill:
                    if bad_argv:
                        with self.assertRaisesRegex(RuntimeError, "shell argv mismatch"):
                            owned.launch(script, "lane", ["sample"], subshell=True)
                        fixture.table.assert_not_called()
                    else:
                        pids = owned.launch(script, "lane", ["sample"], subshell=subshell)
                        self.assertEqual(pids, (101, 102, 103) if subshell else (101, 103))
                        fixture.table.assert_called_once_with(owned.records)
                    self.assertEqual(set(owned.records), {"101", "102", "103"} if subshell else {"101", "103"})
                    self.assertIn('sleep 300 &\necho "$!" > "$CHILD_FILE"\nwait\n', script.read_text())
                    self.assertEqual(') &\necho "$!" > "$SHELL_FILE"\nwait\n' in script.read_text(), subshell)
                    self.assertEqual(launch.call_args.args[0][-3:], ["/bin/bash", str(script), "sample"])
                    kill.assert_not_called()
                    owned.close()
                    expected = [call(103, signal.SIGCONT), call(103, signal.SIGTERM)]
                    if subshell:
                        expected += [call(102, signal.SIGCONT), call(102, signal.SIGTERM)]
                    self.assertEqual(kill.call_args_list, expected + [call(101, signal.SIGCONT)])
