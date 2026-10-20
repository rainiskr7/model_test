"""Literal characterization of health, thermal and manual-stop state logic."""

from orchestration.tests.lane_guard_check.fixture import Fixture


def process(command, parent=0, stat="S", stamp="Mon Oct 19 00:00:00 2026"):
    return {"cmd": command, "ppid": parent, "stat": stat, "stamp": stamp}


def populated(repo, root, target, name):
    fixture = Fixture(repo, root / name, target)
    fixture.table({"800001": process(fixture.command()),
                   "800002": process("sleep 300", parent=800001)})
    return fixture


def health_case(repo, root, target, report):
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


def duplicate_case(repo, root, target, report):
    f = populated(repo, root, target, "duplicate")
    records = f.records()
    records["800003"] = dict(records["800001"], stamp="second start")
    f.table(records)
    f.values("down", "84 96")
    f.cycle(2)
    report.check("duplicate roots never signalled", not f.signals())
    report.check("duplicate warning once", f.log().count("레인 2개 이상") == 1)


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
