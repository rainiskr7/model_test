"""C6.1/C6.2; all shell runs use temporary copies and fake children.

Old-revision failure reproduction (expected pytest rc 1 before the fix):
SKIP_BENCHES_TEST_REVISION=HEAD bash tests/run_pytests.sh multimodal \
-q -p no:cacheprovider -k test_c61_rejects_before_writes
The revision override affects C6.1 only. Session timestamps are fixed except in
C6.1, where creation itself is the regression being detected.
"""

import contextlib
import io
import re
import shlex
import subprocess

import pytest

from configs import load_model_config
from shared.multimodal.tests.skip_benches_support import (
    Driver, NAMES, selected_source, snapshot, source,
)


def error_text(unknown):
    return (
        f"[run_all] SKIP_BENCHES 에 알 수 없는 이름: {unknown}\n"
        f"사용 가능: {' '.join(NAMES)}\n"
    )


def test_c61_rejects_before_writes(tmp_path):
    driver = Driver(tmp_path / "case", selected_source(), stop=True)
    driver.env.pop("EVAL_TIMESTAMP")
    before = snapshot(driver.root)
    result = driver.run("kretaa")
    session_created = (driver.root / ".eval_session").exists()
    bench_called = "FAKE_BENCH=" in result.stdout
    stop_reached = "FAKE_PY_STOP" in result.stderr
    evidence = (
        f"rc={result.returncode}, session_created={session_created}, "
        f"fake_bench_called={bench_called}, fake_py_stop={stop_reached}"
    )
    # HEAD must fail this assertion with rc=1 and all three flags True.
    assert result.returncode == 2, evidence
    assert result.stdout == ""
    assert result.stderr == error_text("kretaa")
    assert not (session_created or bench_called or stop_reached)
    assert snapshot(driver.root) == before
    assert not any((driver.root / name).exists() for name in ("results", "data", "logs"))


@pytest.mark.parametrize("skip,unknown", [
    ("kretaa", "kretaa"),
    ("kreta typo b4_latency", "typo b4_latency"),
    ("*", "*"),
    ("kreta\t*\nunknown", "* unknown"),
    ("-n %s", "-n %s"),
])
@pytest.mark.parametrize("existing", [False, True], ids=["fresh", "existing"])
def test_invalid_names_leave_files_unchanged(tmp_path, skip, unknown, existing):
    driver = Driver(tmp_path / "case", source(), stop=True)
    driver.env.pop("EVAL_TIMESTAMP")
    # A matching filename makes accidental glob expansion observable.
    (driver.root / "kreta").touch()
    if existing:
        (driver.root / ".eval_session").write_text("previous-session\n")
        for name in ("results", "data", "logs"):
            directory = driver.root / name
            directory.mkdir()
            (directory / "sentinel").write_bytes(b"preserve\n")
    before = snapshot(driver.root)
    result = driver.run(skip)
    assert (result.returncode, result.stdout, result.stderr) == (2, "", error_text(unknown))
    assert snapshot(driver.root) == before


VALID = [None, "", " \t\n ", *NAMES, "kreta koffvqa", " ".join(NAMES),
         "kreta kreta", "\tkreta\nb4_latency_profile  "]


@pytest.mark.parametrize("skip", VALID)
def test_c62_valid_names_preserve_head_behavior(tmp_path, skip):
    previous = Driver(tmp_path / "head", source("HEAD"))
    current = Driver(tmp_path / "current", source())
    old = previous.run(skip)
    new = current.run(skip)
    assert (new.returncode, new.stdout, new.stderr) == (old.returncode, old.stdout, old.stderr)
    assert new.returncode == 0 and new.stderr == ""
    skipped = set((skip or "").split())
    expected = [name for name in NAMES if name not in skipped]
    expected.insert(sum(name not in skipped for name in NAMES[:-1]), "ko_vlm_benchmark")
    assert re.findall(r"^FAKE_BENCH=(.+)$", new.stdout, re.M) == expected
    assert new.stdout.count("— SKIP (SKIP_BENCHES)") == len(skipped)
    assert "FAKE_SANITY\n" in new.stdout
    assert "all benchmarks done (failures=0)" in new.stdout
    assert not any((current.root / name).exists() for name in (".eval_session", "results", "data", "logs"))


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("skip_failure", [False, True])
def test_c62_failure_accumulation_and_skip(tmp_path, name, skip_failure):
    skip = name if skip_failure else ""
    previous = Driver(tmp_path / "head", source("HEAD"))
    current = Driver(tmp_path / "current", source())
    old = previous.run(skip, fail=name)
    new = current.run(skip, fail=name)
    assert (new.returncode, new.stdout, new.stderr) == (old.returncode, old.stdout, old.stderr)
    assert new.returncode == (0 if skip_failure else 1)
    assert "FAKE_SANITY\n" in new.stdout


def test_c62_diffusion_loader_exports_b4_skip(tmp_path, monkeypatch):
    for key in ("BASE_URL_CHAT_OVERRIDE", "BASE_URL_V1_OVERRIDE"):
        monkeypatch.delenv(key, raising=False)
    cfg = load_model_config.load("google_diffusiongemma_26B_A4B_it")
    assert cfg["skip_benches"] == ["b4_latency_profile"]
    assert load_model_config.SKIPPABLE_BENCHES == frozenset({"b4_latency_profile"})
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        load_model_config.emit_shell(cfg)
    exports = output.getvalue()
    assert "export SKIP_BENCHES=b4_latency_profile\n" in exports
    driver = Driver(tmp_path / "case", source())
    result = driver.run("kreta invalid-inherited-value", shell_exports=exports)
    assert result.returncode == 0 and result.stderr == ""
    assert "FAKE_BENCH=kreta\n" in result.stdout
    assert "FAKE_BENCH=b4_latency_profile\n" not in result.stdout
    assert "=== B-4 Latency Profile — SKIP (SKIP_BENCHES) ===" in result.stdout
    assert "FAKE_SANITY\n" in result.stdout


def test_skip_name_array_matches_hooks():
    text = source()
    declaration = re.search(r"^SKIP_BENCH_NAMES=\(([^)]*)\)$", text, re.M)
    assert declaration is not None
    names = shlex.split(declaration.group(1))
    hooks = re.findall(r"^if skip_bench ([a-z0-9_]+); then$", text, re.M)
    assert len(names) == len(set(names)) == len(NAMES)
    assert set(names) == set(hooks) == set(NAMES)


@pytest.mark.parametrize("noglob", [False, True])
@pytest.mark.parametrize("skip", ["", "kreta", " \t\n"])
def test_validator_preserves_glob_option(tmp_path, noglob, skip):
    # Only the actual startup section, before session handling, is sourced here.
    prefix, separator, _ = source().partition("# 동일 timestamp 공유:")
    assert separator
    driver = Driver(tmp_path / "case", prefix + '\nprintf "FLAGS=%s\\n" "$-"\n')
    result = subprocess.run(
        ["/bin/bash", *(["-f"] if noglob else []), str(driver.script), "m"],
        cwd=driver.root, env={**driver.env, "SKIP_BENCHES": skip},
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0 and result.stderr == ""
    assert ("f" in result.stdout.removeprefix("FLAGS=").strip()) == noglob
