"""Checkout boundaries, literal path escaping, and the HEAD regression."""

from orchestration.tests.lane_guard_check.fixture import Fixture
from orchestration.tests.lane_guard_check.model_cases import process


def regression_case(repo, root, target, old, report):
    # The historical global-match bug is independent of the 5b CLI change.
    # HEAD is still read once; a fixed HEAD must retain isolation, not fail it.
    for label, code in (("HEAD", old), ("working", target)):
        f = Fixture(repo, root / ("regression_" + label), code)
        expected = "없음" if "LANES_LOGICAL=" in code.read_text() else "800009"
        f.table({"800009": process(f.command(root / "outside"))})
        f.cycle()
        report.check("C1.2 " + label + " root=" + expected,
                     f"root={expected} " in f.log() and not f.signals())


def path_case(repo, root, target, report):
    # Deliberately exercise ERE metacharacters and spaces in directory names.
    f = Fixture(repo, root / "literal space.[x]+(y){z}$^", target)
    link = root / "logical_alias"
    link.symlink_to(f.base, target_is_directory=True)
    guard = link / "orchestration/lane_guard.sh"
    for label, directory in (("logical", link), ("physical", f.base.resolve())):
        f.table({"800001": process(f.command(directory))})
        f.cycle(guard=guard)
        report.check(label + " literal directory accepted", "root=800001 " in f.log())
        (f.base / "guard.log").unlink()
        f.table({"800001": process(f.command(directory) + " extra")})
        f.cycle(guard=guard)
        report.check(label + " unsupported directory accepted",
                     "root=없음 " in f.log() and "미지원 실행 형태" in f.log())
        (f.base / "guard.log").unlink()
        for path in (f.base / "state").glob("*"):
            path.unlink()
    # A near-match must not be admitted by an unescaped dot/bracket expression.
    wrong = str(f.base).replace("space.", "spaceX")
    f.table({"800009": process(f.command(wrong))})
    f.cycle(guard=guard)
    report.check("regex near-match excluded", "root=없음 " in f.log() and "미지원" not in f.log())


def unsupported_case(repo, root, target, report):
    f = Fixture(repo, root / "unsupported.[x]+", target, pattern="qwen35fp8")
    exact = f"{f.orch}/lanes/kmmlu.sh"
    commands = [("longer basename", exact.replace(".sh", "_full.sh") + " qwen35fp8", False),
                ("suffix", exact + "suffix qwen35fp8", False),
                ("other checkout", str(root / "other/orchestration/lanes/kmmlu.sh") + " qwen35fp8 extra", False),
                ("other model", exact + " another_model", False),
                ("model prefix", exact + " qwen35fp8_extra", False),
                ("missing argument", exact, True),
                ("extra argument", exact + " qwen35fp8 extra", True),
                ("bash option", "-x " + exact + " qwen35fp8", True)]
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
    report.check("synthetic lanes.conf default", f"{f.name}: 레인 식별 root=없음" in f.log())
