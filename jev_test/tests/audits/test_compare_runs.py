"""무엇: C2 허용 필드 회귀 · 입력: 합성 직접/파생 run · 출력: 수치 변경 실패 · 계약 §9 C2."""

import pytest
from audits.stage2_20261021.compare_runs import compare_runs, compare_tables, main
from jeveval.io import run_files
from tests.audits.stage2_support import copied
from tests.run.history_support import finished


@pytest.mark.parametrize('derived', [False, True])
def test_valid_run_normalization_and_original_hash_check(tmp_path, monkeypatch, derived):
    h = finished(tmp_path, monkeypatch, 'kosgd', 'full')
    if derived:
        h.variant = 'actions_only'; h.finish()
    old, new = copied(h)
    assert compare_runs(old, new) == []
    assert main(['--old-run', str(old), '--new-run', str(new)]) == 0
    folder = new / h.directory.relative_to(old)
    value = run_files.read_json(folder / 'threshold.json')
    value['dev_input']['sha256'] = '0'*64
    run_files.write_json(folder / 'threshold.json', value)
    with pytest.raises(ValueError): compare_runs(old, new)


@pytest.mark.parametrize('field,value', [('n_accepted', 123), ('n_denom', 321), ('status', 'MEETS')])
def test_statistical_changes_fail(tmp_path, monkeypatch, field, value):
    h = finished(tmp_path, monkeypatch)
    old, new = copied(h); folder = new / h.directory.relative_to(old)
    path = folder / 'risk.json'; risk = run_files.read_json(path)
    cell = risk['cells']['0.02']
    if field == 'status': cell[field] = value
    else: cell['test'][field] = value
    run_files.write_json(path, risk)
    assert any(p.endswith('risk.json') for p in compare_runs(old, new))


def test_seven_comparisons_and_seed_changes(tmp_path):
    old, new = tmp_path / 'old', tmp_path / 'new'
    for root in (old, new):
        for i in range(7):
            p = root / f'A/s{i}/default/compare.json'; p.parent.mkdir(parents=True)
            run_files.write_json(p, dict(schema='compare/1', seed=123, n=10))
    assert compare_tables(old, new) == []
    run_files.write_json(new / 'A/s0/default/compare.json', dict(schema='compare/1', seed=124, n=10))
    assert compare_tables(old, new) == ['A/s0/default/compare.json']
