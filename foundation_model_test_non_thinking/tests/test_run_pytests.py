"""Selector contracts only; fake Python never executes pytest, a lane, or a guard.

The pre-change HEAD (94707d2) pins the old CLI for the 13 legacy track names.
All shell execution and writes stay in tmp_path, outside the operational tree.
"""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
LEGACY_TRACKS = {
    **{name: f"shared/{name}" for name in (
        "agent", "functionchat", "taubench", "multimodal", "nlu", "harness",
        "jsonwrite", "publish", "resultspath",
    )},
    "configs": "configs", "reports": "reports", "orchestration": "orchestration",
    "baseline": "tools/output_baseline",
}


@pytest.fixture
def checkout(tmp_path):
    base = tmp_path / "checkout with spaces"
    (base / "tests").mkdir(parents=True)
    shutil.copyfile(ROOT / "tests/run_pytests.sh", base / "tests/run_pytests.sh")
    (base / "pytest.ini").write_text("[pytest]\n")
    for directory in LEGACY_TRACKS.values():
        target = base / directory / "tests"
        target.mkdir(parents=True)
        (target / "test_sample.py").write_text("raise AssertionError('must not import')\n")
    python = base / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text(
        '#!/bin/bash\n'
        'printf "%s\\0" "$PWD" "$@" > "$SELECTOR_CAPTURE"\n'
        'exit "${SELECTOR_RC:-0}"\n'
    )
    python.chmod(0o755)
    return base


def invoke(base, *args, rc=0):
    capture = base / "capture"
    capture.unlink(missing_ok=True)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(base), "LC_ALL": "C",
           "SELECTOR_CAPTURE": str(capture), "SELECTOR_RC": str(rc)}
    result = subprocess.run(
        ["/bin/bash", str(base / "tests/run_pytests.sh"), *args],
        cwd=base.parent, env=env, capture_output=True, timeout=10,
    )
    argv = capture.read_bytes().split(b"\0")[:-1] if capture.exists() else None
    return (result.returncode, result.stdout, result.stderr), argv


@pytest.fixture(scope="module")
def legacy_source():
    return subprocess.run(
        ["git", "show", "94707d2:./tests/run_pytests.sh"], cwd=ROOT,
        check=True, capture_output=True,
    ).stdout


@pytest.mark.parametrize("track,target", LEGACY_TRACKS.items())
def test_legacy_tracks_preserve_target_and_arguments(checkout, legacy_source, track, target):
    args = (track, "-q", "-k", "two words", "--maxfail=1")
    current = invoke(checkout, *args)
    (checkout / "tests/run_pytests.sh").write_bytes(legacy_source)
    assert current == invoke(checkout, *args)
    assert current == ((0, b"", b""), [os.fsencode(str(value)) for value in (
        checkout, "-m", "pytest", "-c", checkout / "pytest.ini", "--rootdir",
        checkout, checkout / target, *args[1:],
    )])


@pytest.mark.parametrize("name,filename", [
    ("jsonread", "test_reader.py"), ("reproidentity", "identity_test.py"),
    ("new_track_2", "test_new.py"),
])
def test_dynamic_tracks_and_list_agree(checkout, name, filename):
    directory = checkout / "shared" / name / "nested"
    directory.mkdir(parents=True)
    (directory / filename).write_text("raise AssertionError('must not import')\n")
    outcome, argv = invoke(checkout, name, "-q")
    assert outcome == (0, b"", b"")
    assert argv[-2:] == [os.fsencode(checkout / "shared" / name), b"-q"]
    outcome, argv = invoke(checkout, "--list")
    assert outcome == (0, ("\n".join(sorted([*LEGACY_TRACKS, name])) + "\n").encode(), b"")
    assert argv is None


def test_list_only_available_tracks_without_python(checkout):
    shutil.rmtree(checkout / ".venv")
    (checkout / "shared/empty").mkdir()
    (checkout / "shared/empty/helper.py").write_text("")
    (checkout / "shared/empty/test_directory.py").mkdir()
    (checkout / "shared/bad-name").mkdir()
    (checkout / "shared/bad-name/test_bad.py").write_text("")
    outcome, argv = invoke(checkout, "--list")
    assert outcome == (0, ("\n".join(sorted(LEGACY_TRACKS)) + "\n").encode(), b"")
    assert argv is None


@pytest.mark.parametrize("name", ["unknown", "../agent", "agent/", "UPPER", "bad-name", "empty"])
def test_unknown_names_are_rejected_without_python(checkout, name):
    (checkout / "shared/empty").mkdir()
    outcome, argv = invoke(checkout, name)
    assert outcome == (2, b"", f"Unknown test track: {name}\n".encode())
    assert argv is None


@pytest.mark.parametrize("args", [(), ("-q",), ("-k", "two words"), ("--", "some/path")])
def test_no_track_and_options_preserve_argv_and_child_rc(checkout, legacy_source, args):
    current = invoke(checkout, *args, rc=23)
    (checkout / "tests/run_pytests.sh").write_bytes(legacy_source)
    assert current == invoke(checkout, *args, rc=23)
    assert current[0] == (23, b"", b"")


@pytest.mark.parametrize("alias", ["configs", "reports", "orchestration", "baseline"])
def test_alias_priority_and_missing_directory(checkout, alias):
    target = LEGACY_TRACKS[alias]
    shadow = checkout / "shared" / alias
    shadow.mkdir()
    (shadow / "test_shadow.py").write_text("")
    assert invoke(checkout, alias)[1][-1] == os.fsencode(checkout / target)
    shutil.rmtree(checkout / target)
    assert invoke(checkout, alias) == (
        (2, b"", f"Test track directory unavailable: {target}\n".encode()), None,
    )
    outcome, argv = invoke(checkout, "--list")
    assert outcome[0] == 0 and alias.encode() not in outcome[1].splitlines()
    assert argv is None


def test_list_rejects_extra_arguments(checkout):
    assert invoke(checkout, "--list", "-q") == (
        (2, b"", b"Usage: run_pytests.sh --list\n"), None,
    )
