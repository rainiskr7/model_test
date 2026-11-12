"""입력: 두 wrapper와 timeout env. 출력: Python argv의 NUL 구분 byte와 rc.

실제 Python 모듈은 실행하지 않는다. wrapper 사본과 PATH의 가짜 python은
tmp_path 안에서만 실행한다. MM_TIMEOUT_TEST_ROOT로 변경 전 소스와 짝 비교 가능.
미설정 argv 기대값은 변경 전 wrapper의 호출 형식을 고정한 것이다.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[3]
MODEL = "fixture model/한글"
BASE_URL = "http://unused.invalid/v1"
DEFAULT_URL = "http://172.16.1.81:18090/v1"
BENCHES = (
    ("k_dtcbench", "K_DTCBENCH_TIMEOUT"),
    ("k_mmbench", "K_MMBENCH_TIMEOUT"),
)
FAKE_PYTHON = r'''#!/bin/sh
printf '%s\0' "$@" > "$FIXTURE_ARGV"
exit "${FIXTURE_RC:-0}"
'''


def run_wrapper(tmp_path, bench, variable, timeout=None, *, with_url=True,
                extra=(), python_rc=0):
    """격리한 wrapper를 실행하고 프로세스 결과와 기록된 argv byte를 반환한다."""
    base = tmp_path.resolve()
    assert not base.is_relative_to(REPO), "fixture must stay outside the repository"
    source = Path(os.environ.get("MM_TIMEOUT_TEST_ROOT", REPO))
    script_dir = base / "shared/multimodal"
    (script_dir / "benches").mkdir(parents=True)
    script = script_dir / f"run_{bench}.sh"
    shutil.copyfile(source / "shared/multimodal" / script.name, script)
    bin_dir = base / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "python"
    fake.write_text(FAKE_PYTHON, encoding="utf-8")
    fake.chmod(0o755)
    record = base / "argv.bin"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.defpath}",
        "MODEL_TEST_BASE": str(base),
        "EVAL_TIMESTAMP": "fixture-session",
        "PYTHONDONTWRITEBYTECODE": "1",
        "FIXTURE_ARGV": str(record),
        "FIXTURE_RC": str(python_rc),
        "LC_ALL": "C",
    }
    if timeout is not None:
        env[variable] = timeout
    command = ["/bin/bash", str(script), MODEL]
    if with_url:
        command.append(BASE_URL)
    command.extend(extra)
    result = subprocess.run(command, cwd=base, env=env, capture_output=True,
                            check=False, timeout=10)
    return result, record.read_bytes() if record.exists() else None


def expected_argv(bench, *, with_url=True, timeout=None, extra=()):
    """문자열 인자 경계를 보존한 기존 호출 및 timeout 추가 기대값."""
    args = ["-m", f"shared.multimodal.benches.{bench}", "--model", MODEL,
            "--base-url", BASE_URL if with_url else DEFAULT_URL]
    if timeout is not None:
        args.extend(("--timeout", timeout))
    if bench == "k_mmbench":
        args.extend(extra)
    return b"\0".join(arg.encode("utf-8") for arg in args) + b"\0"


@pytest.mark.parametrize("bench,variable", BENCHES)
@pytest.mark.parametrize("with_url,extra", [
    (False, ()),
    (True, ()),
    (True, ("--categories", "chart, table", "--timeout", "17.5")),
])
def test_unset_preserves_exact_argv(tmp_path, bench, variable, with_url, extra):
    result, argv = run_wrapper(tmp_path, bench, variable, with_url=with_url, extra=extra)
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == b""
    assert argv == expected_argv(bench, with_url=with_url, extra=extra)


@pytest.mark.parametrize("bench,variable", BENCHES)
@pytest.mark.parametrize("value", ["180", "180.5", ".5", "1.", "+2", "1e2"])
def test_positive_timeout_is_forwarded(tmp_path, bench, variable, value):
    extra = ("--categories", "chart, table")
    result, argv = run_wrapper(tmp_path, bench, variable, value, extra=extra)
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == b""
    assert argv == expected_argv(bench, timeout=value, extra=extra)


@pytest.mark.parametrize("bench,variable", BENCHES)
@pytest.mark.parametrize("value", ["abc", "0", "-1", "", "0.0", "nan", "inf",
                                   "1e309", "1e-999"])
def test_invalid_timeout_rejected_before_python(tmp_path, bench, variable, value):
    result, argv = run_wrapper(tmp_path, bench, variable, value)
    assert result.returncode == 2, result.stderr
    assert result.stdout == b""
    assert variable.encode() in result.stderr
    assert b"positive finite number" in result.stderr
    assert argv is None, "invalid input must not invoke Python"


@pytest.mark.parametrize("bench,variable", BENCHES)
def test_python_exit_status_is_preserved(tmp_path, bench, variable):
    result, argv = run_wrapper(tmp_path, bench, variable, "180", python_rc=7)
    assert result.returncode == 7, result.stderr
    assert argv == expected_argv(bench, timeout="180")
