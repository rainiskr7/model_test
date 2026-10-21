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


def test_audit_only_report_checks_exactly_three_changed_lines(tmp_path):
    from audits.stage2_20261021.compare_runs import compare_audit_report
    prefix = '미완·한계: {model} kosgd/actions_only 사후 감사 v4; file=a.json; sha256=abc; script=def.'
    old_tail = ' 저장 호출과의 연결 미확인: 기존 실행 입력에 대한 뒷받침이 부족하다.\n'
    new_tail = (' 파생 변형: 자체 전송 없음. 파생 출처 검증 PASS. 원천 full 저장 호출 연결 PASS.'
                ' 이어지는 actions_only 규칙은 가상 직접 요청 감사이며 파생 판 자체 전송의 증거가 아님.\n')
    old = '# report\n\n' + ''.join(prefix.format(model=m) + old_tail for m in ('a', 'b', 'c'))
    new = '# report\n\n' + ''.join(prefix.format(model=m) + new_tail for m in ('a', 'b', 'c'))
    assert not compare_audit_report(old, new)
    assert compare_audit_report(old, new.replace('# report', '# report '))
    assert compare_audit_report(old, new.replace('연결 PASS', '연결 FAIL', 1))
    assert compare_audit_report(old, new.replace('file=a.json', 'file=b.json', 1))
    assert compare_audit_report(old, new.replace('\n\n', '\n'))
    a, b = tmp_path / 'old.md', tmp_path / 'new.md'; a.write_text(old); b.write_text(new)
    assert main(['--audit-only-report', '--old-report', str(a), '--new-report', str(b)]) == 0
