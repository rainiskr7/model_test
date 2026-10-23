"""Input: fixture launch requests; output: verified owned trees and PID-only cleanup."""

import os
import signal
import subprocess
import time

from orchestration.tests.lane_guard_check.report import Inconclusive


def ps_field(pid, field):
    """Read one field for one known PID; never enumerate the process table."""
    try:
        result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", field + "="],
                                capture_output=True, text=True, env={"LC_ALL": "C"})
    except PermissionError as exc:
        raise Inconclusive(f"owned-PID ps unavailable: {exc}") from exc
    if result.returncode and "not permitted" in result.stderr.lower():
        raise Inconclusive(result.stderr.strip())
    return result.stdout.strip()


def current_record(pid, expected):
    """Reject disappeared/reused PIDs before reading commands or signalling."""
    stamp = ps_field(pid, "lstart")
    if not stamp or stamp != expected["stamp"]:
        return None
    stat = ps_field(pid, "stat")
    if not stat or "Z" in stat:
        return None
    return dict(expected, stat=stat, cmd=ps_field(pid, "command"), ppid=ps_field(pid, "ppid"))


class Owned:
    def __init__(self, fixture):
        self.fixture = fixture
        self.processes = []
        self.records = {}

    def launch(self, script, name, arguments=(), subshell=False):
        """Input: lane argv/tree shape; output: registered root[, shell], sleep PIDs."""
        marker = self.fixture.base / (name + ".child")
        shell_marker = self.fixture.base / (name + ".subshell")
        script.parent.mkdir(parents=True, exist_ok=True)
        body = 'sleep 300 &\necho "$!" > "$CHILD_FILE"\nwait\n'
        if subshell:
            body = '(\n' + body + ') &\necho "$!" > "$SHELL_FILE"\nwait\n'
        script.write_text('#!/bin/bash\n' + body)
        env = {"PATH": "/usr/bin:/bin", "CHILD_FILE": str(marker),
               "SHELL_FILE": str(shell_marker), "LC_ALL": "C"}
        with (self.fixture.base / (name + ".out")).open("w") as output:
            proc = subprocess.Popen(["/usr/bin/nohup", "/usr/bin/perl", "-e",
                                     "setpgrp; exec @ARGV", "/bin/bash", str(script), *arguments],
                                    env=env, cwd=self.fixture.base, stdin=subprocess.DEVNULL,
                                    stdout=output, stderr=subprocess.STDOUT)
        self.processes.append(proc)
        self.records[str(proc.pid)] = {"ppid": os.getpid(), "stamp": ps_field(proc.pid, "lstart")}
        deadline = time.monotonic() + 5
        markers = [marker, shell_marker] if subshell else [marker]
        while proc.poll() is None and time.monotonic() < deadline:
            # Opening the marker precedes echo's write: existence alone is not readiness.
            if all(path.exists() and path.read_text().strip().isdigit() for path in markers):
                break
            time.sleep(.02)
        # Register every published PID before validation so finally/close can clean up.
        shell = int(shell_marker.read_text()) if subshell and shell_marker.exists() else None
        child = int(marker.read_text()) if marker.exists() else None
        family = [(proc.pid, os.getpid())]
        if shell is not None:
            family.append((shell, proc.pid))
        if child is not None:
            family.append((child, shell if subshell else proc.pid))
        for pid, parent in family:
            self.records[str(pid)] = {"ppid": parent, "stamp": ps_field(pid, "lstart")}
        if child is None or (subshell and shell is None):
            raise RuntimeError(f"fixture lane failed to start: {name}, rc={proc.poll()}")
        if not all(self.records[str(pid)]["stamp"] for pid, _ in family):
            raise Inconclusive("owned PID start identity unavailable")
        rows = [current_record(str(pid), self.records[str(pid)]) for pid, _ in family]
        expected_command = " ".join(("/bin/bash", str(script), *arguments))
        if any(row is None or row["ppid"] != str(parent)
               for row, (_, parent) in zip(rows, family)):
            raise RuntimeError("fixture tree is not alive with the declared parents")
        if rows[0]["cmd"] != expected_command or (subshell and rows[1]["cmd"] != expected_command):
            raise RuntimeError("fixture shell argv mismatch")
        if rows[-1]["cmd"] != "sleep 300":
            raise RuntimeError("fixture sleep argv mismatch")
        self.fixture.table(self.records)
        return tuple(pid for pid, _ in family)

    def states(self, pids):
        return [current_record(pid, self.records[str(pid)]) for pid in pids]

    def close(self):
        # No process-group/global signalling. Resume and kill registered children
        # first, then allow bash to reap them before terminating any remaining root.
        roots = {str(proc.pid) for proc in self.processes}
        # Signal leaves before intermediate shells (including the optional subshell).
        for pid, record in reversed(list(self.records.items())):
            if current_record(pid, record):
                os.kill(int(pid), signal.SIGCONT)
                if pid not in roots:
                    os.kill(int(pid), signal.SIGTERM)
        for proc in self.processes:
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                record = self.records.get(str(proc.pid))
                if record is None or current_record(proc.pid, record):
                    proc.terminate()
                proc.wait(timeout=3)
