"""무엇: 변형 증거 읽기 · 입력: 합성 run/손상 · 출력: 상태와 쓰기 보호 · 계약 §7-4d."""

import pytest
from jeveval.io import analysis_artifacts
from tests.run.analysis_support import prepared, thresholds


def test_evidence_bound_and_new_file_only(tmp_path, monkeypatch):
    h = prepared(tmp_path, monkeypatch); thresholds(h)
    e = analysis_artifacts.read(tmp_path, h.directory)
    assert not e['errors'] and e['manifest'].endswith('score_variants_v1.yaml')
    with pytest.raises(ValueError): analysis_artifacts.write_new(h.directory, 'variant_threshold.json', {})
    (h.directory / 'variant_threshold.json').write_text('{')
    assert analysis_artifacts.read(tmp_path, h.directory)['errors']
