"""Fixture ps/pgrep/kill: JSON model or an explicit real PID allowlist."""

import json
import os
from pathlib import Path
import re
import signal
import sys

from orchestration.tests.lane_guard_check.owned import current_record


def select_pids(records, mode, value):
    """Implement the two guard pgrep forms over a bounded process table."""
    if mode == "-f":
        return [pid for pid, row in records.items() if re.search(value, row["cmd"])]
    if mode == "-P":
        return [pid for pid, row in records.items() if str(row["ppid"]) == value]
    raise ValueError(f"unsupported pgrep mode: {mode}")


def ps_output(records, args):
    """Format only the exact ps forms used by the guard."""
    if args == ["-axo", "command="]:
        return "\n".join(row["cmd"] for row in records.values())
    if len(args) != 4 or args[0] != "-p" or args[2] != "-o":
        raise ValueError(f"unsupported ps args: {args}")
    pid, field = args[1], args[3]
    if field == "pid=":
        # This is the guard's own availability probe, not a table search.
        return pid if pid == os.environ.get("LG_CHECK_GUARD_PID") else ""
    row = records.get(pid)
    return "" if row is None else row[{"lstart=": "stamp", "stat=": "stat",
                                       "command=": "cmd"}[field]]


def send_signal(base, data, records, args, real):
    """Log every attempt, and refuse any PID outside the live ownership set."""
    sig, pid = args
    allowed = pid in records and sig in ("-STOP", "-CONT")
    with (base / "signals.jsonl").open("a") as output:
        output.write(json.dumps({"signal": sig, "pid": pid, "allowed": allowed}) + "\n")
    if not allowed:
        return 1
    if real:
        # Recheck start identity immediately before the real signal.
        if current_record(pid, data["processes"][pid]) is None:
            return 1
        os.kill(int(pid), getattr(signal, "SIG" + sig[1:]))
    else:
        data["processes"][pid]["stat"] = "T" if sig == "-STOP" else "S"
        (base / "processes.json").write_text(json.dumps(data))
    return 0


def main():
    base = Path(os.environ["LG_CHECK_BASE"])
    tool, *args = sys.argv[1:]
    with (base / "calls.jsonl").open("a") as output:
        output.write(json.dumps([tool, *args]) + "\n")
    data = json.loads((base / "processes.json").read_text())
    real = os.environ["LG_CHECK_MODE"] == "real"
    records = data["processes"]
    if real:
        records = {pid: row for pid, expected in records.items()
                   if (row := current_record(pid, expected)) is not None}
    if tool == "kill":
        return send_signal(base, data, records, args, real)
    if tool == "pgrep":
        result = "\n".join(select_pids(records, *args))
    elif tool == "ps":
        result = ps_output(records, args)
    else:
        raise ValueError(f"forbidden tool: {tool}")
    if result:
        print(result)
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
