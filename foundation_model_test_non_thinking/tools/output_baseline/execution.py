"""Subprocess evidence; selected code is imported only in its own process."""

import hashlib
import os
import subprocess
import time
from pathlib import Path

from tools.output_baseline.inputs import sha256


def environment(code, base):
    env = os.environ.copy()
    env.update(PYTHONPATH=str(code), MODEL_TEST_BASE=str(base),
               PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0")
    return env


def command(argv, code, base, logdir):
    logdir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        result = subprocess.run(argv, cwd=code, env=environment(code, base),
                                capture_output=True, timeout=900)
        rc, stdout, stderr = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        rc, stdout, stderr = 124, exc.stdout or b"", exc.stderr or b""
    (logdir / "stdout").write_bytes(stdout)
    (logdir / "stderr").write_bytes(stderr)
    return {"argv": [str(arg) for arg in argv], "cwd": str(code), "rc": rc,
            "elapsed_seconds": time.monotonic() - started,
            "stdout_path": str(logdir / "stdout"), "stderr_path": str(logdir / "stderr")}


class Runner:
    def __init__(self, base, code, snapshot, output, python):
        self.base, self.code, self.snapshot = base, code, snapshot
        self.output, self.python = output, python
        self.record = {"code_root": str(code), "output_root": str(output),
                       "runs": {}, "artifacts": {}, "errors": []}

    def run(self, name, args, accepted=(0,)):
        token = hashlib.sha256(name.encode()).hexdigest()[:20]
        record = command([str(self.python), "-B", *args], self.code, self.base,
                         self.output / "logs" / token)
        self.record["runs"][name] = record
        if record["rc"] not in accepted:
            self.record["errors"].append(f"{name}: execution rc {record['rc']}")
        return record

    def artifact(self, name, path, rc):
        if not path.is_file():
            self.record["errors"].append(f"missing output: {name}")
            return
        self.record["artifacts"][name] = {"path": str(path), "rc": rc, "sha256": sha256(path)}
