"""C5: disposable dry-run checkout; no production input, credentials or runtime IO.

The identical defect assertion can be run against the pre-fix entry by A:
LOADER_STDERR_REVISION=73c9540 bash tests/run_pytests.sh orchestration \
    -q -p no:cacheprovider -k test_missing_config_diagnostic
This must FAIL on the missing diagnostic, not xfail or invert its assertion.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONF = ("CONFIG=missing_model\nHOST_ENV=FIXTURE_HOST\nHOST_DEFAULT=fixture.invalid:1\n"
        "KEYVAR=FIXTURE_KEY\nLANE_DISPLAY=fixture\nSESSION_KMMLU=fixture\n"
        "LANE_TOKENIZER=unused\nREPS=1\n")
YAML = "model: fixture/model\ntokenizer_path: fixture-tokenizer\nclass: llm\ntracks: []\n"


def checkout(tmp_path, *, source=None, config="missing_model"):
    """Copy only loader/lane sources; even the real loader uses synthetic YAML."""
    root = tmp_path / "checkout"
    for directory in ("orchestration/lanes", "orchestration/models", "orchestration/tracks",
                      "configs/models", "configs/serving_profiles", ".venv/bin", "bin"):
        (root / directory).mkdir(parents=True)
    (root / "orchestration/run_lane.sh").write_bytes(
        source if source is not None else (ROOT / "orchestration/run_lane.sh").read_bytes())
    (root / "orchestration/lanes/kmmlu.sh").symlink_to("../run_lane.sh")
    shutil.copytree(ROOT / "orchestration/laneconf", root / "orchestration/laneconf",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("orchestration/tracks/kmmlu.sh", "configs/load_model_config.py"):
        shutil.copyfile(ROOT / name, root / name)
    (root / "orchestration/models/sample.conf").write_text(
        CONF.replace("CONFIG=missing_model", "CONFIG=" + config))
    (root / "configs/models/available.yaml").write_text(YAML)
    for name in ("bin/python", ".venv/bin/python"):
        path = root / name
        path.write_text("#!/bin/bash\nexec " + shlex.quote(sys.executable) + ' -B "$@"\n')
        path.chmod(0o755)
    (root / ".venv/bin/activate").write_text(
        "export PATH=" + shlex.quote(str(root / "bin") + ":/usr/bin:/bin") + "\n")
    for name in ("curl", "grep", "mktemp"):
        path = root / "bin" / name
        path.write_text("#!/bin/bash\nprintf 'FORBIDDEN " + name + "\\n' >&2\nexit 97\n")
        path.chmod(0o755)
    return root


def snapshot(root):
    return {str(path.relative_to(root)): (os.readlink(path) if path.is_symlink()
            else path.read_bytes() if path.is_file() else None) for path in root.rglob("*")}


def dry_run(root, extra=None):
    """Run only the disposable entry, asserting no file creation or input mutation."""
    before = snapshot(root)
    env = dict(PATH="/usr/bin:/bin", HOME=str(root), LC_ALL="C", PYTHONPATH=str(root),
               PYTHONDONTWRITEBYTECODE="1", LANE_DRY_RUN="1", TMPDIR=str(root / "logs"))
    result = subprocess.run(["/bin/bash", str(root / "orchestration/lanes/kmmlu.sh"), "sample"],
                            cwd=root.parent, env={**env, **(extra or {})},
                            capture_output=True, timeout=15)
    assert snapshot(root) == before
    assert not any((root / name).exists() for name in (".env", "logs", "results", "data"))
    assert b"FORBIDDEN" not in result.stderr
    return result


def stub_loader(root, stderr, rc, stdout=""):
    (root / "configs/load_model_config.py").write_text(
        "import sys\n" + f"sys.stdout.write({stdout!r})\nsys.stderr.write({stderr!r})\n"
        + f"raise SystemExit({rc})\n")


def test_missing_config_diagnostic(tmp_path):
    source = None
    revision = os.environ.get("LOADER_STDERR_REVISION")
    if revision:
        source = subprocess.run(["git", "show", f"{revision}:./orchestration/run_lane.sh"],
                                cwd=ROOT, capture_output=True, check=True).stdout
    root = checkout(tmp_path, source=source)
    result = dry_run(root)
    assert result.returncode == 1 and result.stdout == b""
    assert "config 없음".encode() in result.stderr
    assert b"CONFIG=missing_model, rc=1" in result.stderr
    assert "사용 가능: ['available']".encode() in result.stderr


@pytest.mark.parametrize("stub", [False, True])
def test_success_discards_stderr_and_preserves_stdout(tmp_path, stub):
    root = checkout(tmp_path, config="available")
    if stub:
        stub_loader(root, "printf poisoned > should_not_exist\n", 0,
                    "export MODEL=fixture/model\n"
                    "export BASE_URL_CHAT=http://fixture.invalid:1/v1/chat/completions\n")
    result = dry_run(root)
    expected = (f"BASE={root}\nconf={root}/orchestration/models/sample.conf\n"
                "HOST=fixture.invalid:1\nSESSION=fixture_r1\n"
                "COMMAND=bash vsm/harness/run_harness.sh fixture/model unused "
                "http://fixture.invalid:1/v1/chat/completions\n").encode()
    assert (result.returncode, result.stdout, result.stderr) == (0, expected, b"")


@pytest.mark.parametrize("stderr", ["", "원인", "원인\n", "원인\n\n", ".\n",
                                    "긴 줄" * 3000, "control\x1b[31m\r\ttext\n"])
def test_failure_preserves_text_and_never_evaluates_partial_stdout(tmp_path, stderr):
    root = checkout(tmp_path)
    stub_loader(root, stderr, 7, 'printf evaluated > "$MODEL_TEST_BASE/evaluated"\n')
    result = dry_run(root)
    expected = "run_lane: model config loader failed (CONFIG=missing_model, rc=7)\n" + stderr
    assert (result.returncode, result.stdout, result.stderr) == (1, b"", expected.encode())


@pytest.mark.parametrize("rc", [1, 2, 127])
def test_all_loader_failures_keep_lane_rc_one(tmp_path, rc):
    root = checkout(tmp_path)
    stub_loader(root, "failure\n", rc)
    result = dry_run(root)
    assert result.returncode == 1 and result.stdout == b""
    assert f"rc={rc})\nfailure\n".encode() in result.stderr


@pytest.mark.parametrize("first,second", [("short", "short-long"), ("short-long", "short"),
                                          ("key[*]?\\value", "judge&key"), ("", "judge-key")])
def test_redacts_known_literal_keys_in_header_and_stderr(tmp_path, first, second):
    config = "missing_" + (first or "none") + "_" + second
    root = checkout(tmp_path, config=config)
    stub_loader(root, f"first={first}; second={second}\n\n", 7)
    result = dry_run(root, dict(OPENAI_API_KEY=first, TAUBENCH_USER_API_KEY=second))
    safe_first = "***" if first else "none"
    expected = (f"run_lane: model config loader failed (CONFIG=missing_{safe_first}_***, rc=7)\n"
                f"first={'***' if first else ''}; second=***\n\n")
    assert (result.returncode, result.stdout, result.stderr) == (1, b"", expected.encode())


def test_real_yaml_error_redacts_input_snippet(tmp_path):
    root = checkout(tmp_path, config="available")
    secret = "synthetic-yaml-key"
    (root / "configs/models/available.yaml").write_text(f"api_key: [{secret}\n")
    result = dry_run(root, dict(OPENAI_API_KEY=secret))
    assert result.returncode == 1 and result.stdout == b""
    assert b"Traceback" in result.stderr and b"***" in result.stderr
    assert secret.encode() not in result.stderr
