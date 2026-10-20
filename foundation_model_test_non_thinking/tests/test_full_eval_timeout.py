"""Collect the standalone, offline full-eval timeout contract in pytest."""
from pathlib import Path
import subprocess
import sys


def test_full_eval_timeouts():
    driver = Path(__file__).with_name("full_eval_timeout_checks.py")
    result = subprocess.run([sys.executable, "-I", str(driver)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
