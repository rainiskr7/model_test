"""Build independent guard trees without reading the production lanes.conf."""

import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def executable(path, source):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    path.chmod(0o755)


def head_guard(repo, artifacts):
    """Read the pre-change file from HEAD, accounting for N's Git prefix."""
    ref = "HEAD:./orchestration/lane_guard.sh"
    result = subprocess.run(["git", "show", ref], cwd=repo, check=True, capture_output=True)
    path = artifacts / "head_lane_guard.sh"
    path.write_bytes(result.stdout)
    (artifacts / "head_source.txt").write_text(f"git show {ref}\nrc={result.returncode}\n")
    return path


class Fixture:
    def __init__(self, repo, base, target, mode="model", pattern="qwen38"):
        self.base = base
        self.orch = base / "orchestration"
        (self.orch / "lanes").mkdir(parents=True)
        shutil.copyfile(target, self.orch / "lane_guard.sh")
        helper = base / "shared/harness/harness_lib.sh"
        helper.parent.mkdir(parents=True)
        shutil.copyfile(repo / "shared/harness/harness_lib.sh", helper)
        self.lanes = f"fixture|{pattern}|fixture.invalid|FIXTURE_KEY|fixture-model"
        (self.orch / "lanes.conf").write_text(self.lanes + "\n")
        self.table({})
        self.env = self.environment(repo, mode)
        self.install_adapters()
        self.values("up", "60 70")

    def environment(self, repo, mode):
        return {"PATH": f"{self.base}/bin:/usr/bin:/bin", "HOME": str(self.base),
                "LC_ALL": "C", "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1",
                "LG_CHECK_BASE": str(self.base), "LG_CHECK_MODE": mode,
                "BASH_ENV": str(self.base / "hook.sh"), "LANEGUARD_ONCE": "1",
                "LANEGUARD_LANES": self.lanes,
                "LANEGUARD_RUNTIME_DIR": str(self.base / "runtime"),
                "LANEGUARD_STATE_DIR": str(self.base / "state"),
                "LANEGUARD_LOG": str(self.base / "guard.log"),
                "LANEGUARD_HEALTH_CMD": str(self.base / "health"),
                "LANEGUARD_TEMP_CMD": str(self.base / "temp")}

    def install_adapters(self):
        module = "orchestration.tests.lane_guard_check.adapter"
        for tool in ("ps", "pgrep", "kill"):
            executable(self.base / "bin" / tool,
                       f"#!/bin/bash\nexec {shlex.quote(sys.executable)} -B -m {module} {tool} \"$@\"\n")
        # Bash's kill builtin otherwise bypasses PATH. No production variable or
        # production code hook is added; BASH_ENV exists only in the fixture env.
        (self.base / "hook.sh").write_text(
            'enable -n kill\nexport LG_CHECK_GUARD_PID=${LG_CHECK_GUARD_PID:-$$}\n')
        executable(self.base / "health", '#!/bin/bash\n[ "$(cat "$LG_CHECK_BASE/health_value")" = up ]\n')
        executable(self.base / "temp", '#!/bin/bash\ncat "$LG_CHECK_BASE/temp_value"\n')
        for tool in ("curl", "dscacheutil"):
            executable(self.base / "bin" / tool,
                       '#!/bin/bash\necho forbidden >> "$LG_CHECK_BASE/network_attempts"\nexit 97\n')

    def table(self, records):
        (self.base / "processes.json").write_text(json.dumps({"processes": records}))

    def records(self):
        return json.loads((self.base / "processes.json").read_text())["processes"]

    def values(self, health, temperature):
        (self.base / "health_value").write_text(health)
        (self.base / "temp_value").write_text(temperature)

    def cycle(self, count=1, guard=None):
        for _ in range(count):
            result = subprocess.run(["/bin/bash", str(guard or self.orch / "lane_guard.sh")],
                                    cwd=self.base, env=self.env, capture_output=True,
                                    text=True, timeout=30)
            with (self.base / "cycles.log").open("a") as output:
                output.write(f"rc={result.returncode}\n{result.stdout}{result.stderr}")
            if result.returncode:
                raise RuntimeError(f"guard rc={result.returncode}: {result.stdout}{result.stderr}")
        if (self.base / "network_attempts").exists():
            raise RuntimeError("unexpected network command")

    def log(self):
        return (self.base / "guard.log").read_text()

    def signals(self):
        path = self.base / "signals.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def stopped(self):
        return all("T" in row["stat"] for row in self.records().values())
