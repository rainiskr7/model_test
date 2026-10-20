"""무엇: C2 증거 선검사 · 입력: 합성 run/손상 · 출력: 해시·크기 거부 · 계약 §9 C2."""

import pytest
from audits.stage2_20261021.compare_evidence import variant, parse
from jeveval.io import run_files
from tests.run.history_support import finished


def test_actual_size_checked_before_normalizing(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    assert variant(h.directory)[0]['run_id'] == 'r1'
    p = h.directory / 'threshold.json'; value = run_files.read_json(p)
    value['dev_input']['nbytes'] += 1; run_files.write_json(p, value)
    with pytest.raises(ValueError, match='dev evidence'): variant(h.directory)


def test_duplicate_and_nonfinite_json_refused():
    for value in ('{"a":1,"a":2}', '{"a":NaN}'):
        with pytest.raises(ValueError): parse(value)


def test_artifact_whitespace_is_not_an_allowed_field_change(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    path = h.directory / 'scores.json'
    path.write_bytes(path.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='noncanonical'): variant(h.directory)
