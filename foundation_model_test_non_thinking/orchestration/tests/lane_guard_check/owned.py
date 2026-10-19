"""Inspect and clean up only explicitly launched fixture processes."""

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
    return dict(expected, stat=stat, cmd=ps_field(pid, "command"))


class Owned:
    def __init__(self, fixture):
        self.fixture = fixture
        self.processes = []
        self.records = {}

    def launch(self, script, name):
        """Use the production nohup/perl/exec form with one declared sleep child."""
        marker = self.fixture.base / (name + ".child")
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text('#!/bin/bash\nsleep 300 &\necho "$!" > "$CHILD_FILE"\nwait\n')
        env = {"PATH": "/usr/bin:/bin", "CHILD_FILE": str(marker), "LC_ALL": "C"}
        with (self.fixture.base / (name + ".out")).open("w") as output:
            proc = subprocess.Popen(["/usr/bin/nohup", "/usr/bin/perl", "-e",
                                     "setpgrp; exec @ARGV", "/bin/bash", str(script)],
                                    env=env, cwd=self.fixture.base, stdin=subprocess.DEVNULL,
                                    stdout=output, stderr=subprocess.STDOUT)
        self.processes.append(proc)
        self.records[str(proc.pid)] = {"ppid": os.getpid(), "stamp": ps_field(proc.pid, "lstart")}
        deadline = time.monotonic() + 5
        while not marker.exists() and proc.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        if not marker.exists():
            raise RuntimeError(f"fixture lane failed to start: {name}, rc={proc.poll()}")
        child = int(marker.read_text())
        for pid, parent in ((proc.pid, os.getpid()), (child, proc.pid)):
            self.records[str(pid)] = {"ppid": parent, "stamp": ps_field(pid, "lstart")}
        if ps_field(child, "ppid") != str(proc.pid):
            raise RuntimeError("fixture child parent mismatch")
        self.fixture.table(self.records)
        return proc.pid, child

    def states(self, pids):
        return [current_record(pid, self.records[str(pid)]) for pid in pids]

    def close(self):
        # No process-group/global signalling. Resume and kill registered children
        # first, then allow bash to reap them before terminating any remaining root.
        roots = {str(proc.pid) for proc in self.processes}
        for pid, record in self.records.items():
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
