"""Importing preflight must not inspect argv or open the manifest."""

import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "benches" / "b3_preflight.py"


def test_preflight_import_without_arguments_is_silent(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"""
import importlib.util
spec = importlib.util.spec_from_file_location("preflight", {str(SCRIPT)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
"""], cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


@pytest.mark.parametrize("missing", [False, True])
def test_preflight_cli_keeps_output_and_exit_code(tmp_path, missing):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{"image": "image.png"}, {}]), encoding="utf-8")
    if not missing:
        (tmp_path / "image.png").touch()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(manifest), str(tmp_path)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert result.stdout == ("NO\n" if missing else "OK\n")
    assert result.stderr == (
        f"[run_all] B-3 preflight 실패: 이미지 누락\n  - {tmp_path / 'image.png'}\n" if missing else ""
    )
