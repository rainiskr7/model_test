"""Real STOP/CONT evidence with no global process enumeration."""

import json
import os
import re
import threading

from orchestration.tests.lane_guard_check.fixture import Fixture
from orchestration.tests.lane_guard_check.owned import Owned, ps_field
from orchestration.tests.lane_guard_check.report import Inconclusive


class DecoyMonitor:
    def __init__(self, pids):
        self.pids = pids
        self.samples = []
        self.errors = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.watch, daemon=True)

    def watch(self):
        try:
            while not self.stop.is_set():
                self.samples.append({str(pid): ps_field(pid, "stat") for pid in self.pids})
                self.stop.wait(.05)
        except Exception as exc:
            self.errors.append(repr(exc))

    def close(self, path):
        self.stop.set()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError("decoy monitor did not stop")
        path.write_text(json.dumps({"samples": self.samples, "errors": self.errors}, indent=2))


def require_tree(report, name, owned, pids, stopped):
    records = owned.states(pids)
    report.check(name, all(row and (("T" in row["stat"]) == stopped) for row in records))


def real_case(repo, root, target, report, label, physical=True, decoy=True):
    # Check before launch: denied inspection must never leave a spawned tree.
    if ps_field(os.getpid(), "pid") != str(os.getpid()):
        raise Inconclusive("owned-PID ps probe did not return this driver PID")
    f = Fixture(repo, root / label, target, mode="real")
    owned, monitor = Owned(f), None
    try:
        lane = f.orch / "lanes/qwen38.sh"
        lane = lane.resolve() if physical else lane
        pids = owned.launch(lane, "lane")
        if not all(row["stamp"] for row in owned.records.values()):
            raise Inconclusive("owned PID start identity unavailable")
        if decoy:
            bait = root / "outside" / label / "orchestration/lanes/qwen38.sh"
            decoys = owned.launch(bait.resolve(), "decoy")
            monitor = DecoyMonitor(decoys)
            monitor.thread.start()
        exercise_tree(f, owned, pids, report, label)
        if monitor:
            monitor.close(f.base / "decoy_samples.json")
            report.check(label + " C1.1 decoy T=0 / exited=0",
                         bool(monitor.samples) and not monitor.errors and
                         all(stat and "T" not in stat and "Z" not in stat
                             for sample in monitor.samples for stat in sample.values()))
            report.check(label + " C1.1 decoy log PID=0",
                         all(not re.search(rf"\b{pid}\b", f.log()) for pid in decoys))
            report.check(label + " decoy signal attempts=0",
                         not any(int(s["pid"]) in decoys for s in f.signals()))
    finally:
        try:
            if monitor:
                monitor.close(f.base / "decoy_samples.json")
        finally:
            owned.close()


def exercise_tree(f, owned, pids, report, label):
    f.cycle()
    report.check(label + " C1.3 owned root identified", f"root={pids[0]} " in f.log())
    f.values("up", "84 70")
    f.cycle()
    require_tree(report, label + " C1.3 STOP root + sleep", owned, pids, True)
    f.values("up", "72 85")
    f.cycle(2)
    require_tree(report, label + " two cool cycles stay stopped", owned, pids, True)
    f.cycle()
    require_tree(report, label + " C1.3 third cool cycle CONT", owned, pids, False)
    report.check(label + " only owned signals allowed", all(s["allowed"] for s in f.signals()))
