"""무엇: 보조 보고 검증 · 입력: 새/옛/손상 합성 run · 출력: 독립 절 · 계약 §7-6."""

from jeveval.io import history, run_files
from jeveval.run import cmd_report, cmd_score_variants
from tests.run.history_support import finished
from tests.run.analysis_support import prepared, thresholds


def test_old_run_power_and_invalid_selective_hidden(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    (h.directory / 'selective.json').unlink()
    value = cmd_report._variant(tmp_path, h.directory)
    assert value.selective.status == 'missing' and value.selective.power
    (h.directory / 'selective.json').write_text('{')
    value = cmd_report._variant(tmp_path, h.directory)
    assert value.status == 'verified_complete' and value.selective.status == 'invalid'


def test_registered_variant_report_recomputes_and_hides_tampering(tmp_path, monkeypatch):
    h = prepared(tmp_path, monkeypatch); thresholds(h); h.run('test'); h.command('score')
    cmd_score_variants.run(root=tmp_path, run_dir=h.directory)
    assert cmd_report._variant(tmp_path, h.directory).score_variants.status == 'registered'
    path = h.directory / 'score_variants.json'; value = run_files.read_json(path)
    value['cells']['0.02']['test']['n_accepted'] = 10000
    run_files.write_json(path, value)
    result = cmd_report._variant(tmp_path, h.directory)
    assert result.status == 'verified_complete'
    assert result.score_variants.status == 'registration_damaged' and not result.score_variants.cells


def test_derived_report_note(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch, 'kosgd', 'full')
    h.variant = 'actions_only'; h.finish()
    assert '파생 변형' in cmd_report._variant(tmp_path, h.directory).score_variants.note
