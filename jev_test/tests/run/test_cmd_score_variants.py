"""무엇: 확신 명령 통합 · 입력: 등록/역사 합성 run · 출력: 주 바이트 보존 · 계약 §7-4d."""

import pytest
from jeveval.io import run_files
from jeveval.run import cli, cmd_score_variants
from tests.run.analysis_support import prepared, thresholds
from tests.run.history_support import finished


def test_registered_risk_preserves_primary_and_cli(tmp_path, monkeypatch):
    h = prepared(tmp_path, monkeypatch); thresholds(h); h.run('test'); h.command('score')
    before = (h.directory / 'risk.json').read_bytes()
    assert cli.main(['score-variants', 'risk', '--run-dir', str(h.directory)]) == 0
    value = run_files.read_json(h.directory / 'score_variants.json')
    assert value['registration']['status'] == 'registered'
    assert set(value['cells']) == {'0.01', '0.02', '0.05'}
    assert (h.directory / 'risk.json').read_bytes() == before
    with pytest.raises(ValueError): cmd_score_variants.run(root=tmp_path, run_dir=h.directory, mode='threshold')


def test_history_exploratory_and_no_overwrite(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    assert cmd_score_variants.run(root=tmp_path, run_dir=h.directory, history=True)['registration'] == 'exploratory'
    before = (h.directory / 'score_variants.json').read_bytes()
    with pytest.raises(ValueError): cmd_score_variants.run(root=tmp_path, run_dir=h.directory, history=True)
    assert (h.directory / 'score_variants.json').read_bytes() == before
    with pytest.raises(ValueError): cmd_score_variants.run(root=tmp_path, run_dir=h.directory, mode='threshold')


def test_history_derived_is_explicitly_unsupported(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch, 'kosgd', 'full')
    h.variant = 'actions_only'; h.finish()
    with pytest.raises(ValueError, match='derived variant'):
        cmd_score_variants.run(root=tmp_path, run_dir=h.directory, history=True)
    assert not (h.directory / 'score_variants.json').exists()
