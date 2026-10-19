"""Checkout boundaries, literal path escaping, and the HEAD regression."""

from orchestration.tests.lane_guard_check.fixture import Fixture
from orchestration.tests.lane_guard_check.model_cases import process


def regression_case(repo, root, target, old, report):
    decoy = root / "outside/orchestration/lanes/qwen38.sh"
    # The pre-fix FAIL was demonstrated once before commit 8dd8b82. Once HEAD
    # carries the fix, only the isolation PASS remains a meaningful regression check.
    cases = [("after", target, "없음")]
    if old.read_bytes() != target.read_bytes():
        cases.insert(0, ("before", old, "800009"))
    else:
        print("NOTE C1.2 before-check skipped: HEAD guard == target", flush=True)
    for label, code, expected in cases:
        f = Fixture(repo, root / ("regression_" + label), code)
        f.table({"800009": process(f"/bin/bash {decoy}")})
        f.cycle()
        report.check("C1.2 " + label + " root=" + expected,
                     f"root={expected} " in f.log() and not f.signals(),
                     "isolation FAIL (expected regression)" if label == "before" else "isolation PASS")


def path_case(repo, root, target, report):
    # Deliberately exercise ERE metacharacters and spaces in directory names.
    f = Fixture(repo, root / "literal space.[x]+(y){z}$^", target)
    link = root / "logical_alias"
    link.symlink_to(f.base, target_is_directory=True)
    guard = link / "orchestration/lane_guard.sh"
    for label, directory in (("logical", link), ("physical", f.base.resolve())):
        f.table({"800001": process(f"/bin/bash {directory}/orchestration/lanes/qwen38.sh")})
        f.cycle(guard=guard)
        report.check(label + " literal directory accepted", "root=800001 " in f.log())
        (f.base / "guard.log").unlink()
        f.table({"800001": process(f"/bin/bash {directory}/orchestration/lanes/qwen38.sh extra")})
        f.cycle(guard=guard)
        report.check(label + " unsupported directory accepted",
                     "root=없음 " in f.log() and "미지원 실행 형태" in f.log())
        (f.base / "guard.log").unlink()
        for path in (f.base / "state").glob("*"):
            path.unlink()
    # A near-match must not be admitted by an unescaped dot/bracket expression.
    wrong = str(f.base).replace("space.", "spaceX")
    f.table({"800009": process(f"/bin/bash {wrong}/orchestration/lanes/qwen38.sh")})
    f.cycle(guard=guard)
    report.check("regex near-match excluded", "root=없음 " in f.log() and "미지원" not in f.log())


def unsupported_case(repo, root, target, report):
    f = Fixture(repo, root / "unsupported.[x]+", target, pattern="qwen35fp8")
    exact = f"{f.orch}/lanes/qwen35fp8.sh"
    commands = [("longer basename", exact.replace(".sh", "_full.sh"), False),
                ("suffix", exact + "suffix", False),
                ("other checkout", str(root / "other/orchestration/lanes/qwen35fp8.sh") + " extra", False),
                ("extra argument", exact + " extra", True),
                ("bash option", "-x " + exact, True)]
    for label, command, warned in commands:
        for path in (f.base / "state").glob("*"):
            path.unlink()
        (f.base / "guard.log").unlink(missing_ok=True)
        f.table({"800009": process("/bin/bash " + command)})
        f.cycle()
        report.check("unsupported boundary: " + label,
                     ("미지원 실행 형태" in f.log()) == warned and "root=없음 " in f.log()
                     and not f.signals())


def default_conf_case(repo, root, target, report):
    f = Fixture(repo, root / "synthetic_default", target)
    del f.env["LANEGUARD_LANES"]
    f.cycle()
    report.check("synthetic lanes.conf default", "fixture: 레인 식별 root=없음" in f.log())
