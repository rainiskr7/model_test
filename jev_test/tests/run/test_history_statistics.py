"""무엇: 역사 집계 연결 검사 · 입력: 손상 수치 · 출력: 고정 거부 · 계약 §5-1b."""

import pytest

from jeveval.io import history, run_files
from jeveval.run.history_check import check
from tests.run.history_support import finished


def test_public_numeric_field_cannot_contain_original_text(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    path = h.directory / "scores.json"
    value = run_files.read_json(path)
    value["populations"]["test"]["questions"]["answerable"]["accuracy"]["num"] = "PRIVATE_RAW"
    run_files.write_json(path, value)
    assert check(history.read(tmp_path, h.directory)).status == "damaged"
