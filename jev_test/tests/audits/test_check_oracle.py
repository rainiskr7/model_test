"""무엇: oracle CLI 조립 · 입력: 합성 완료 run · 출력: 원문 없는 대조 결과 · 계약 §9 C3."""

from audits.stage2_20261021.check_oracle import check, main
from jeveval.io import run_files
from tests.run.history_support import finished


def test_actual_synthetic_run_and_tamper(tmp_path, monkeypatch, capsys):
    h = finished(tmp_path, monkeypatch)
    assert check(tmp_path, h.directory) == []
    assert main(['--root', str(tmp_path), '--run-dir', str(h.directory)]) == 0
    path = h.directory / 'selective.json'
    value = run_files.read_json(path); value['partial_aurc'] = .5
    run_files.write_json(path, value)
    assert check(tmp_path, h.directory) == ['partial_aurc']
    capsys.readouterr()
    assert main(['--root', str(tmp_path), '--run-dir', 'missing']) == 1
    assert 'oracle inputs' in capsys.readouterr().out
