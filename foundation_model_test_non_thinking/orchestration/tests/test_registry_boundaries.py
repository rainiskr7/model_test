"""Track registration observes only valid file names in the executing tree."""
import subprocess

import pytest

from orchestration.tests.laneconf_support import REPO, SAMPLE
from orchestration.tests.lane_guard_check.fixture import Fixture as GuardFixture
from orchestration.tests.registry_support import RegistryComparison


@pytest.mark.parametrize('track,kind,accepted', [
    ('demo', 'file', True), ('demo', 'link', True), ('demo', 'directory', False),
    ('demo', 'broken', False), ('Bad', 'file', False), ('bad-name', 'file', False),
    ('bad.name', 'file', False), ('_9', 'file', True),
])
def test_registry_runner_guard_cli_share_file_rule(tmp_path, track, kind, accepted):
    guard = GuardFixture(REPO, tmp_path / 'checkout', REPO / 'orchestration/lane_guard.sh')
    fx = RegistryComparison(guard.base)
    # This content must never be sourced by guard, even when it is a valid file.
    target = fx.orch / 'tracks' / (track + '.sh')
    poison = fx.put('poison', 'exit 97\n')
    if kind == 'file':
        target.write_text('exit 97\n')
    elif kind == 'link':
        target.symlink_to(poison)
    elif kind == 'broken':
        target.symlink_to('absent')
    else:
        target.mkdir()
    (fx.orch / 'lanes' / (track + '.sh')).symlink_to('../run_lane.sh')
    session = 'SESSION_' + track.upper()
    fx.put('orchestration/models/sample.conf', SAMPLE + session + '=fixture\n')
    guard.env['LANEGUARD_LANES'] = f'sample_{track}|{track}|sample|fixture.invalid|FIXTURE_KEY|fixture-model'
    if accepted:
        guard.cycle()  # A sourced poison file would exit 97 instead.
        assert fx.cli('sample', track).returncode == 0
        assert fx.lane('sample', track).returncode == 97  # Runner does source the registered file.
    else:
        with pytest.raises(RuntimeError, match='guard rc=4:'):
            guard.cycle()
        assert fx.cli('sample', track).returncode == 2
        assert fx.lane('sample', track).returncode == 2
    assert not guard.signals() and not (fx.base / 'network_attempts').exists()



def test_missing_track_dry_run_fails_instead_of_silent_success(tmp_path):
    """A track file that forgets track_dry_run must exit 2, not print and succeed."""
    guard = GuardFixture(REPO, tmp_path / 'checkout', REPO / 'orchestration/lane_guard.sh')
    fx = RegistryComparison(guard.base)
    fx.install('working')
    (fx.orch / 'tracks' / 'demo.sh').write_text('track_run() { echo defined; }\n')
    (fx.orch / 'lanes' / 'demo.sh').symlink_to('../run_lane.sh')
    fx.put('orchestration/models/sample.conf', SAMPLE + 'SESSION_DEMO=fixture\n')
    result = fx.lane('sample', 'demo')
    assert result.returncode == 2
    assert result.stderr.endswith(b'run_lane: track demo defines no track_dry_run\n')


def test_missing_track_run_fails_before_preflight_and_lock(tmp_path):
    """CH2: a missing hook must fail before the real path can acquire resources."""
    from orchestration.tests.host_lock_fixture import Fixture as LaneFixture
    fx = LaneFixture(tmp_path)
    try:
        fx.put('orchestration/tracks/demo.sh', 'track_dry_run() { echo defined; }\n')
        path = fx.lane('demo', 'demo')
        result = subprocess.run(['/bin/bash', str(path), 'demo'], cwd=fx.base, timeout=60,
                                env=dict(fx.env, LANE_DRY_RUN='0'), capture_output=True)
        assert result.returncode == 2, result.stdout + result.stderr
        assert result.stderr.endswith(b'run_lane: track demo defines no track_run\n')
        assert not (fx.base / 'preflights').exists()
        assert not (fx.base / 'logs').exists()
    finally:
        fx.close()
