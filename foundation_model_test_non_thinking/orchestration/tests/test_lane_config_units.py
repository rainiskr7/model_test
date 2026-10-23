"""5b entry arguments and literal model/track settings in an isolated BASE."""

import subprocess

import pytest

from orchestration.tests.host_lock_fixture import Fixture


@pytest.fixture
def lane(tmp_path):
    fx = Fixture(tmp_path)
    fx.lane('sample', 'kmmlu')
    yield fx
    fx.close()


def run(fx, arguments, track='kmmlu'):
    script = fx.base / 'orchestration/lanes' / (track + '.sh')
    if not script.is_symlink():
        script.symlink_to('../run_lane.sh')
    result = subprocess.run(['/bin/bash', str(script), *arguments], cwd=fx.base,
                            env=dict(fx.env, LANE_DRY_RUN='1'), capture_output=True, text=True)
    assert not (fx.base / 'logs').exists()
    assert not (fx.base / 'preflights').exists()
    return result


@pytest.mark.parametrize('arguments', [[], ['sample', 'extra'], [''], ['sample.conf'],
                                      ['../sample'], ['a/b'], ['A'], ['a-b'], ['a b']])
def test_invalid_model_arguments_fail_before_activation(lane, arguments):
    assert run(lane, arguments).returncode == 2


def test_missing_conf_and_unknown_track(lane):
    missing = run(lane, ['missing'])
    assert missing.returncode == 2 and 'missing conf:' in missing.stderr
    unknown = run(lane, ['sample'], 'unknown')
    assert unknown.returncode == 2 and 'unknown TRACK: unknown' in unknown.stderr


@pytest.mark.parametrize('track', ['kmmlu', 'taubench_std4', 'full'])
def test_selected_track_requires_its_session(lane, track):
    conf = lane.base / 'orchestration/models/sample.conf'
    conf.write_text(conf.read_text().replace('SESSION_KMMLU=sample\n', ''))
    result = run(lane, ['sample'], track)
    assert result.returncode == 2
    assert 'required key: SESSION_' + track.upper() in result.stderr


@pytest.mark.parametrize('scoped_first', [True, False])
def test_scoped_settings_override_common_without_cross_track_leak(lane, scoped_first):
    conf = lane.base / 'orchestration/models/sample.conf'
    common = 'REPS=2\nAGENT_REQUEST_TIMEOUT=310\n'
    scoped = 'FULL_REPS=1\nFULL_AGENT_REQUEST_TIMEOUT=350\nFULL_AGENT_TASK_TIMEOUT=1000\n'
    # Replace the common value: duplicate assignments are now configuration errors.
    conf.write_text(conf.read_text().replace('REPS=1\n', '') + 'SESSION_FULL=full_session\n' +
                    (scoped + common if scoped_first else common + scoped))
    kmmlu = run(lane, ['sample'])
    full = run(lane, ['sample'], 'full')
    assert kmmlu.returncode == full.returncode == 0
    assert kmmlu.stdout.count('SESSION=') == 2
    assert full.stdout.count('SESSION=') == 2
    assert 'SESSION=full_session_tbstd4\n' in full.stdout
    assert 'AGENT_REQUEST_TIMEOUT=350 AGENT_TASK_TIMEOUT=1000' in full.stdout


@pytest.mark.parametrize('setting', ['TRACK=full', 'SESSION=x', 'FULL_LANE_DISPLAY=x', 'FULL_UNKNOWN=x'])
def test_unsupported_conf_keys_rejected(lane, setting):
    conf = lane.base / 'orchestration/models/sample.conf'
    conf.write_text(conf.read_text() + setting + '\n')
    assert run(lane, ['sample']).returncode == 2


def test_literal_value_is_not_shell_evaluated(lane):
    conf = lane.base / 'orchestration/models/sample.conf'
    conf.write_text(conf.read_text().replace('LANE_TOKENIZER=unused\n',
                                             'LANE_TOKENIZER="$(touch unexpected)"\n'))
    result = run(lane, ['sample'])
    assert result.returncode == 0 and '$(touch unexpected)' in result.stdout
    assert not (lane.base / 'unexpected').exists()
