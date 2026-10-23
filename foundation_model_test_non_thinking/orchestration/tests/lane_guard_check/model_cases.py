"""Input: synthetic process tables/health/heat; output: guard state and signal assertions."""

from orchestration.tests.lane_guard_check.fixture import Fixture


def process(command, parent=0, stat="S", stamp="Mon Oct 19 00:00:00 2026"):
    return {"cmd": command, "ppid": parent, "stat": stat, "stamp": stamp}


def populated(repo, root, target, name):
    fixture = Fixture(repo, root / name, target)
    fixture.table({"800001": process(fixture.command()),
                   "800002": process("sleep 300", parent=800001)})
    return fixture


def health_case(repo, root, target, report, defect=None):
    f = populated(repo, root, target, "health")
    f.cycle()
    report.check("model identification", "root=800001 " in f.log())
    f.values("down", "60 70")
    f.cycle()
    report.check("health first failure does not STOP", not f.signals())
    f.cycle()
    report.check("health second failure stops root and child", f.stopped())
    f.values("up", "60 70")
    f.cycle()
    report.check("health first success retains STOP", f.stopped())
    f.cycle()
    report.check("health second success resumes tree", all(r["stat"] == "S" for r in f.records().values()))
    report.check("CONT children before root", [s["pid"] for s in f.signals()
                                             if s["signal"] == "-CONT"] == ["800002", "800001"])
    for label, code in (("defect", defect), ("working", target)):
        if code is None:
            continue
        f = Fixture(repo, root / ("subshell_health_" + label), code)
        f.table({"800001": process(f.command()),
                 "800004": process(f.command(), parent=800001),
                 "800005": process("sleep 300", parent=800004)})
        f.values("down", "60 70")
        f.cycle(2)  # cycle raises on nonzero guard rc: a fixture error is not reproduction.
        if label == "defect":
            report.check("C1 defect acceptance FAIL reproduced: rc=0, duplicate, no signals",
                         f.log().count("레인 2개 이상") == 1 and not f.signals() and
                         all(row["stat"] == "S" for row in f.records().values()))
            continue
        report.check("C1 parent root identified without duplicate/unsupported warnings",
                     "root=800001 " in f.log() and "레인 2개 이상" not in f.log() and "미지원" not in f.log())
        report.check("C1 three owned PIDs stopped", f.stopped() and
                     [s["pid"] for s in f.signals() if s["signal"] == "-STOP"] ==
                     ["800001", "800004", "800005"])
        f.values("up", "60 70")
        f.cycle()
        report.check("C1 first healthy cycle retains all held entries", f.stopped())
        f.cycle()
        report.check("C1 second healthy cycle resumes children before root",
                     all(row["stat"] == "S" for row in f.records().values()) and
                     [s["pid"] for s in f.signals() if s["signal"] == "-CONT"] ==
                     ["800005", "800004", "800001"])


def heat_case(repo, root, target, report, hot, label):
    f = populated(repo, root, target, label)
    f.values("up", "83 95")
    f.cycle()
    report.check(label + " below high boundaries", not f.signals())
    f.values("up", hot)
    f.cycle()
    report.check(label + " exact high threshold STOP", f.stopped())
    f.values("up", "72 85")
    f.cycle(2)
    report.check(label + " two cool readings keep STOP", f.stopped())
    f.values("up", "")
    f.cycle()
    state = (f.base / "state" / (f.name + ".state")).read_text().splitlines()[0].split("|")
    report.check(label + " read failure keeps heat and resets cool", state[3] == "1" and state[6] == "0")
    f.values("up", "72 85")
    f.cycle(2)
    report.check(label + " recovery needs three fresh readings", f.stopped())
    f.cycle()
    report.check(label + " third cool reading CONT", all(r["stat"] == "S" for r in f.records().values()))


def manual_case(repo, root, target, report):
    f = populated(repo, root, target, "manual")
    records = f.records()
    records["800002"]["stat"] = "T"
    f.table(records)
    f.cycle()
    report.check("manual STOP observed", "사람이 확인 pid=800002" in f.log())
    f.values("up", "84 70")
    f.cycle()
    f.values("up", "72 85")
    f.cycle(3)
    report.check("manual child never receives guard CONT",
                 f.records()["800002"]["stat"] == "T" and
                 not any(s["pid"] == "800002" for s in f.signals()))
    report.check("owned root recovers beside manual child", f.records()["800001"]["stat"] == "S")
    f = Fixture(repo, root / "orphan_promotion", target)
    f.table({"800001": process(f.command()),
             "800004": process(f.command(), parent=800001),
             "800005": process("sleep 300", parent=800004)})
    f.values("down", "84 96")
    f.cycle(2)
    report.check("C3 tree held before root exit", f.stopped())
    state_path = f.base / "state" / (f.name + ".state")
    old_state = state_path.read_text().splitlines()
    # Seed nonzero recovery counters to prove promotion resets all three counters.
    state = old_state[0].split("|")
    state[5:7] = ["1", "2"]
    state_path.write_text("\n".join(["|".join(state), *old_state[1:]]) + "\n")
    records = f.records()
    del records["800001"]
    records["800004"]["ppid"] = 1
    f.table(records)
    f.values("up", "72 85")
    f.cycle()
    promoted = state_path.read_text().splitlines()
    report.check("C3 orphan promoted; reasons/held retained and counters reset",
                 promoted[0].split("|")[1:] ==
                 ["800004:" + records["800004"]["stamp"], "1", "1", "0", "1", "1"] and
                 all(line in promoted for line in old_state if line.endswith("|held") and
                     not line.startswith("800001|")) and
                 not any(line.startswith("800001|") for line in promoted) and f.stopped())
    f.cycle()
    report.check("C3 promoted tree remains held until third cool cycle", f.stopped())
    f.cycle()
    report.check("C3 promoted root resumed last; exited root never resumed",
                 all(row["stat"] == "S" for row in f.records().values()) and
                 [s["pid"] for s in f.signals() if s["signal"] == "-CONT"] == ["800005", "800004"])


def duplicate_case(repo, root, target, report):
    f = populated(repo, root, target, "duplicate")
    records = f.records()
    records["800003"] = dict(records["800001"], stamp="second start")
    f.table(records)
    f.values("down", "84 96")
    f.cycle(2)
    report.check("duplicate roots never signalled", not f.signals())
    report.check("duplicate warning once", f.log().count("레인 2개 이상") == 1)
    for label, parent, denied in (("empty", "", False), ("denied", 800001, True),
                                  ("invalid", "unknown", False)):
        f = Fixture(repo, root / ("ppid_" + label), target)
        # Inspect the child first: failure on the later candidate must undo filtering.
        f.table({"800004": process(f.command(), parent=800001),
                 "800001": dict(process(f.command(), parent=parent), ppid_error=denied)})
        f.values("down", "84 96")
        f.cycle(2)
        report.check("C3 ppid " + label + " retains original duplicates without unsupported warning",
                     not f.signals() and f.log().count("레인 2개 이상") == 1 and "미지원" not in f.log())


def overlap_case(repo, root, target, report):
    f = populated(repo, root, target, "overlap")
    f.values("down", "84 96")
    f.cycle(2)
    f.values("up", "84 96")
    f.cycle(2)
    report.check("health recovery cannot clear heat STOP", f.stopped())
    f.values("down", "72 85")
    f.cycle(3)
    report.check("heat recovery cannot clear health STOP", f.stopped())
    f.values("up", "72 85")
    f.cycle(2)
    report.check("both reasons cleared resumes tree", all(r["stat"] == "S" for r in f.records().values()))
    f = Fixture(repo, root / "stage_replacement", target)
    f.table({"800001": process(f.command()),
             "800004": process(f.command(), parent=800001),
             "800005": process("sleep 300", parent=800004)})
    f.values("down", "60 70")
    f.cycle()
    state_path = f.base / "state" / (f.name + ".state")
    instance = state_path.read_text().splitlines()[0].split("|")[1]
    records = f.records()
    del records["800004"], records["800005"]
    records.update({"800006": process(f.command(), parent=800001, stamp="next stage"),
                    "800007": process("sleep 300", parent=800006, stamp="next stage")})
    f.table(records)
    f.cycle()
    state = state_path.read_text().splitlines()
    report.check("C3 stage replacement preserves instance/failure counter and stops new tree",
                 state[0].split("|")[1] == instance and state[0].split("|")[4] == "2" and f.stopped())
    held_root = next(line for line in state if line.startswith("800001|"))
    records = f.records()
    # Simulate vanished held children and a new stage; the live root's ownership survives.
    del records["800006"], records["800007"]
    records.update({"800008": process(f.command(), parent=800001, stamp="third stage"),
                    "800009": process("sleep 300", parent=800008, stamp="third stage")})
    f.table(records)
    f.cycle()
    state = state_path.read_text().splitlines()
    report.check("C3 held root retained, stale entries removed, new descendants stopped",
                 state[0].split("|")[1] == instance and state[0].split("|")[4] == "3" and
                 held_root in state and not any(line.startswith(("800006|", "800007|")) for line in state) and
                 f.stopped() and sum(s["signal"] == "-STOP" and s["pid"] == "800001" for s in f.signals()) == 1)
    f.values("up", "60 70")
    f.cycle()
    report.check("C3 first recovery cycle retains held root", held_root in state_path.read_text().splitlines())
    f.cycle()
    report.check("C3 replacement descendants resume before root",
                 all(row["stat"] == "S" for row in f.records().values()) and
                 [s["pid"] for s in f.signals() if s["signal"] == "-CONT"] == ["800009", "800008", "800001"])
