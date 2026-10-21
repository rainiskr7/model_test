"""무엇: 위험 고정점 도구 검증 · 입력: tmp_path 합성 run/변조 · 출력: 통과·차이 · 계약 §9 C7."""

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from audits.stage2_20261021 import check_anchor
from jeveval.io import run_files
from tests.run.history_support import finished


@pytest.mark.parametrize('derived', [False, True])
def test_completed_run_including_derived(tmp_path, monkeypatch, capsys, derived):
    h = finished(tmp_path, monkeypatch, 'kosgd', 'full') if derived else finished(tmp_path, monkeypatch)
    if derived:
        h.variant = 'actions_only'; h.finish()
        assert (h.directory / 'test/derived.json').is_file()
    assert check_anchor.check(tmp_path, h.directory) == []
    capsys.readouterr()
    directory = str(h.directory.relative_to(tmp_path))
    assert check_anchor.main(['--root', str(tmp_path), '--run-dir', directory, '--run-dir', directory]) == 0
    assert json.loads(capsys.readouterr().out) == dict(ok=True, runs=[
        dict(index=0, differences=[]), dict(index=1, differences=[])])


@pytest.mark.parametrize('field', ['n_accepted', 'k_errors', 'n_denom'])
def test_risk_count_tampering_fails(tmp_path, monkeypatch, capsys, field):
    h = finished(tmp_path, monkeypatch)
    path = h.directory / 'risk.json'
    value = run_files.read_json(path)
    assert value['cells']['0.02']['t_star'] is not None
    value['cells']['0.02']['test'][field] += 1
    run_files.write_json(path, value)
    capsys.readouterr()
    assert check_anchor.main(['--root', str(tmp_path), '--run-dir', str(h.directory)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['ok'] is False
    assert f'risk.json.cells.0.02.test.{field}' in result['runs'][0]['differences']


@pytest.mark.parametrize('field', ['partial_aurc', 'power'])
def test_selective_tampering_fails(tmp_path, monkeypatch, field):
    h = finished(tmp_path, monkeypatch)
    path = h.directory / 'selective.json'
    value = run_files.read_json(path)
    if field == 'power':
        value['power']['0.02'][0]['probability'] = .5
    else:
        value[field] = .5
    run_files.write_json(path, value)
    expected = 'selective.json.power.0.02.0.probability' if field == 'power' else 'selective.json.partial_aurc'
    assert check_anchor.check(tmp_path, h.directory) == [expected]


def test_cutoffs_ties_masks_and_exact_threshold():
    rows = [SimpleNamespace(valid=valid, mask_empty=empty, s=s, wrong=wrong)
            for valid, empty, s, wrong in [(True, False, .9, False), (True, False, .9, True),
                (True, False, .4, False), (False, False, None, None), (True, True, .99, False)]]
    risk = dict(cells={t: dict(t_star=.9, test=dict(n_accepted=2, k_errors=1, n_denom=4))
                       for t in ('0.01', '0.02', '0.05')})
    assert check_anchor.risk_differences(rows, risk) == []
    cell = risk['cells']['0.02']
    cell['test']['n_accepted'] = 3  # 다른 관측 cutoff의 n/k라도 t_star와 다르면 거부한다.
    assert check_anchor.risk_differences(rows, risk) == ['risk.json.cells.0.02.test.n_accepted']
    cell['test']['n_accepted'] = 2
    cell['t_star'] = .8  # dev 임계값이 test 관측 점수에 없어도 같은 수락 집합이면 통과한다.
    assert check_anchor.risk_differences(rows, risk) == []


@pytest.mark.parametrize('cutoff,n,k', [(.8, 1, 1), (.95, 0, 0), (.1, 2, 1)])
def test_unobserved_test_threshold_passes(cutoff, n, k):
    rows = [SimpleNamespace(valid=True, mask_empty=False, s=s, wrong=wrong)
            for s, wrong in ((.9, True), (.4, False))]
    risk = dict(cells={t: dict(t_star=cutoff, test=dict(n_accepted=n, k_errors=k, n_denom=2))
                       for t in ('0.01', '0.02', '0.05')})
    assert check_anchor.risk_differences(rows, risk) == []


@pytest.mark.parametrize('cutoff', [float('nan'), float('inf'), -float('inf'), True, '0.8'])
def test_nonfinite_or_non_numeric_threshold_fails(cutoff):
    risk = dict(cells={t: dict(t_star=None, test=dict(n_accepted=None, k_errors=None, n_denom=0))
                       for t in ('0.01', '0.02', '0.05')})
    risk['cells']['0.02']['t_star'] = cutoff
    assert check_anchor.risk_differences([], risk) == ['risk.json.cells.0.02.t_star']


def test_no_threshold_requires_null_acceptance():
    risk = dict(cells={t: dict(t_star=None, test=dict(n_accepted=None, k_errors=None, n_denom=0))
                       for t in ('0.01', '0.02', '0.05')})
    assert check_anchor.risk_differences([], risk) == []
    risk['cells']['0.01']['test']['n_accepted'] = 0
    assert check_anchor.risk_differences([], risk) == ['risk.json.cells.0.01.test.n_accepted']


def test_unreadable_run_keeps_indices_and_hides_exception(tmp_path, monkeypatch, capsys):
    h = finished(tmp_path, monkeypatch)
    completed = check_anchor.context.completed
    def restore(root, directory):
        if directory == 'bad':
            raise ValueError('PRIVATE_QUESTION_CONTENT')
        return completed(root, directory)
    monkeypatch.setattr(check_anchor.context, 'completed', restore)
    capsys.readouterr()
    assert check_anchor.main(['--root', str(tmp_path), '--run-dir', 'bad', '--run-dir', str(h.directory)]) == 1
    text = capsys.readouterr().out
    assert 'PRIVATE_QUESTION_CONTENT' not in text
    assert json.loads(text) == dict(ok=False, runs=[dict(index=0, differences=['inputs']),
                                                  dict(index=1, differences=[])])


def test_tool_avoids_production_selective_power_and_historical_restore():
    tree = ast.parse(Path(check_anchor.__file__).read_text())
    imports = [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    imports += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not any(name.startswith(('jeveval.score.selective', 'jeveval.score.power',
                                   'jeveval.run.history_stage')) for name in imports)
