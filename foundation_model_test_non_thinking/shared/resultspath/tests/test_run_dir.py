"""Scorer and runner resolution priorities, with no real session files."""
import re
from types import SimpleNamespace

import pytest

from shared.resultspath.run_dir import run_timestamp, scoring_results_dir


def args(**overrides):
    return SimpleNamespace(**dict(dict(results_dir=None, model='model/a', timestamp=None, track='test'), **overrides))


def test_explicit_results_dir_wins(tmp_path, monkeypatch):
    monkeypatch.setenv('MODEL_TEST_BASE', str(tmp_path / 'ignored'))
    monkeypatch.delenv('EVAL_TIMESTAMP', raising=False)
    assert scoring_results_dir(args(results_dir=tmp_path, model=None), tmp_path / 'default') == tmp_path.resolve()


@pytest.mark.parametrize('env_base', [False, True])
@pytest.mark.parametrize('explicit_timestamp', [False, True])
def test_base_and_timestamp(tmp_path, monkeypatch, env_base, explicit_timestamp):
    monkeypatch.delenv('MODEL_TEST_BASE', raising=False)
    monkeypatch.setenv('EVAL_TIMESTAMP', 'env-session')
    base = tmp_path / ('env' if env_base else 'default')
    if env_base:
        monkeypatch.setenv('MODEL_TEST_BASE', str(base))
    (base / 'results/Model_A').mkdir(parents=True)
    cli = 'cli-session' if explicit_timestamp else None
    assert scoring_results_dir(args(timestamp=cli), tmp_path / 'default') == base / 'results/Model_A' / (cli or 'env-session') / 'language/test'


@pytest.mark.parametrize('model,timestamp', [(None, 'session'), ('model', None), (None, None)])
def test_missing_arguments(tmp_path, monkeypatch, model, timestamp):
    monkeypatch.delenv('EVAL_TIMESTAMP', raising=False)
    with pytest.raises(ValueError) as exc:
        scoring_results_dir(args(model=model, timestamp=timestamp), tmp_path)
    assert str(exc.value) == '--model and --timestamp (or EVAL_TIMESTAMP) are required'


@pytest.mark.parametrize('case', ['env', 'session', 'now', 'empty-session'])
def test_timestamp(tmp_path, monkeypatch, case):
    monkeypatch.delenv('EVAL_TIMESTAMP', raising=False)
    if case in ('env', 'session'):
        (tmp_path / '.eval_session').write_text(' session-value\n')
    if case == 'empty-session':
        (tmp_path / '.eval_session').write_text(' \n')
    if case == 'env':
        monkeypatch.setenv('EVAL_TIMESTAMP', 'env-value')
    actual = run_timestamp(tmp_path)
    if case in ('now', 'empty-session'):
        assert re.fullmatch(r'\d{8}_\d{6}', actual)
        if case == 'now':
            assert not (tmp_path / '.eval_session').exists()
    else:
        assert actual == ('env-value' if case == 'env' else 'session-value')
