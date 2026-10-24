"""Defaults and scope application preserve the common shell contract."""
import pytest

from orchestration.laneconf import ConfigError, parse, resolve
from orchestration.tests.laneconf_support import SAMPLE, TRACKS


@pytest.mark.parametrize('scoped_first', [False, True])
def test_scope_priority_is_independent_of_order(scoped_first):
    common, scoped = 'REPS=2\nAGENT_REQUEST_TIMEOUT=310\n', 'FULL_REPS=1\nFULL_AGENT_REQUEST_TIMEOUT=350\n'
    entries = parse(SAMPLE + 'SESSION_FULL=full\n' + (scoped + common if scoped_first else common + scoped))
    before = list(entries)
    assert resolve(entries, 'kmmlu', TRACKS)['REPS'] == '2'
    full = resolve(entries, 'full', TRACKS)
    assert (full['REPS'], full['AGENT_REQUEST_TIMEOUT'], full['SESSION']) == ('1', '350', 'full')
    assert entries == before


def test_defaults_empty_values_and_internal_destinations():
    values = resolve(parse(SAMPLE), 'kmmlu', TRACKS)
    assert (values['REPS'], values['NUM_CONCURRENT'], values['LM_EVAL_MODE']) == ('3', '8', 'chat')
    assert (values['FULL_AGENT_TASK_TIMEOUT'], values['FULL_KRETA_WORKERS']) == ('900', '4')
    values = resolve(parse(SAMPLE + 'LM_EVAL_MODE=\nKRETA_WORKERS=2\nFULL_KRETA_WORKERS=3\n'), 'kmmlu', TRACKS)
    assert values['LM_EVAL_MODE'] == ''
    assert values['FULL_KRETA_WORKERS'] == '2'
    assert 'KRETA_WORKERS' not in values
    defaults = resolve(parse(SAMPLE), 'kmmlu', TRACKS)
    assert [defaults[key] for key in ('JUDGE_MODEL', 'JUDGE_PROVIDER', 'JUDGE_REASONING_EFFORT', 'JUDGE_MAX_TOKENS')] == [
        'openai/gpt-4.1-mini', '', '', '']
    for first in (False, True):
        common = 'JUDGE_MODEL=common\nJUDGE_PROVIDER=common\nJUDGE_REASONING_EFFORT=low\nJUDGE_MAX_TOKENS=100\n'
        scoped = 'FULL_JUDGE_MODEL=alias\nFULL_JUDGE_PROVIDER=deepinfra/bf16\nFULL_JUDGE_REASONING_EFFORT=medium\nFULL_JUDGE_MAX_TOKENS=2000\n'
        entries = parse(SAMPLE + 'SESSION_FULL=fixture\n' + (scoped + common if first else common + scoped))
        full = resolve(entries, 'full', TRACKS)
        assert [full[key] for key in ('JUDGE_MODEL', 'JUDGE_PROVIDER', 'JUDGE_REASONING_EFFORT', 'JUDGE_MAX_TOKENS')] == [
            'alias', 'deepinfra/bf16', 'medium', '2000']
        assert resolve(entries, 'kmmlu', TRACKS)['JUDGE_MODEL'] == 'common'


@pytest.mark.parametrize('key', ['CONFIG', 'HOST_ENV', 'HOST_DEFAULT', 'KEYVAR', 'LANE_DISPLAY',
                                 'SESSION_KMMLU', 'SESSION_TAUBENCH_STD4', 'SESSION_FULL'])
def test_track_prefix_forbidden_even_on_unselected_track(key):
    with pytest.raises(ConfigError) as error:
        resolve(parse(SAMPLE + 'FULL_' + key + '=x\n'), 'kmmlu', TRACKS)
    assert str(error.value) == 'key cannot have track prefix: ' + key


@pytest.mark.parametrize('key', ['UNKNOWN', 'full_REPS', 'FULL_UNKNOWN', ' REPS', 'REPS '])
def test_unknown_keys_are_not_silently_filtered(key):
    with pytest.raises(ConfigError, match='unknown key:'):
        resolve(parse(SAMPLE + key + '=1'), 'kmmlu', TRACKS)


def test_session_optional_only_for_smoke_and_track_list_explicit():
    entries = parse(SAMPLE.replace('SESSION_KMMLU=fixture\n', ''))
    assert resolve(entries, 'kmmlu', TRACKS, require_session=False)['SESSION'] == ''
    with pytest.raises(ConfigError, match='required key: SESSION_KMMLU'):
        resolve(entries, 'kmmlu', TRACKS)
    with pytest.raises(ConfigError, match='unknown TRACK: kmmlu'):
        resolve(entries, 'kmmlu', ())


@pytest.mark.parametrize('name,valid', [('KEY', True), ('_KEY', True), ('A:B', True),
                                       ('9KEY', False), ('A:9', False), ('A-B', False)])
def test_environment_name_matches_shell_case(name, valid):
    entries = parse(SAMPLE.replace('KEYVAR=FIXTURE_KEY', 'KEYVAR=' + name))
    if valid:
        assert resolve(entries, 'kmmlu', TRACKS)['KEYVAR'] == name
    else:
        with pytest.raises(ConfigError, match='invalid environment variable name'):
            resolve(entries, 'kmmlu', TRACKS)
