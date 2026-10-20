"""4d: real native locks and owned process groups against synthetic lane inputs."""

import os
import signal

import pytest

from orchestration.tests.host_lock_fixture import Fixture, gone, wait_for

TRACKS = ('kmmlu', 'taubench_std4', 'full')


@pytest.fixture
def fixture(tmp_path):
    fx = Fixture(tmp_path)
    print('ARTIFACTS=' + str(tmp_path), 'HARNESS_LOCK_TOOL=' + str(fx.tool), flush=True)
    try:
        yield fx
    finally:
        fx.close()


def native(fixture):
    if fixture.tool is None:
        pytest.skip('INCONCLUSIVE: no native flock or fd-mode /usr/bin/lockf')


@pytest.mark.parametrize('track', TRACKS)
def test_same_host_excludes_other_track_and_normal_exit_releases(fixture, track):
    native(fixture)
    first = fixture.start('first', track)
    other_track = TRACKS[(TRACKS.index(track) + 1) % len(TRACKS)]
    second = fixture.start('second', other_track)
    # Start both before waiting: either track may win the same-HOST race.
    wait_for(lambda: first.poll() is not None or second.poll() is not None)
    winner, loser = ((first, 'first', track), (second, 'second', other_track))
    if first.poll() is not None:
        winner, loser = loser, winner
    assert loser[0].wait(timeout=5) == 2
    session, record = fixture.ready(winner[1], winner[2], winner[0])
    # 5b: generated log prefix includes the selected track.
    assert 'fixture ' + loser[2] + ': 같은 호스트 레인 실행 중 — 시작 안 함' in fixture.output(loser[1])
    assert len((fixture.base / 'preflights').read_text().splitlines()) == 1
    assert not list((fixture.base / 'records').glob(loser[1] + '*'))
    locks = list((fixture.base / 'logs/resume_orch').glob('.lane_host_*.lock'))
    assert [path.name for path in locks] == ['.lane_host_fixture.invalid_18023.lock']
    fixture.release(session)
    assert winner[0].wait(timeout=5) == 0
    replacement = fixture.start('replacement', loser[2])
    fixture.ready('replacement', loser[2], replacement)


@pytest.mark.parametrize('track', TRACKS)
def test_same_server_different_ports_run_concurrently(fixture, track):
    native(fixture)
    first = fixture.start('port_a', track, 'fixture.invalid:18023')
    fixture.ready('port_a', track, first)
    second = fixture.start('port_b', track, 'fixture.invalid:18024')
    fixture.ready('port_b', track, second)
    assert first.poll() is None and second.poll() is None
    assert len(list((fixture.base / 'logs/resume_orch').glob('.lane_host_*.lock'))) == 2


@pytest.mark.parametrize('track', TRACKS)
def test_group_term_reaps_owned_children_and_releases_lock(fixture, track):
    native(fixture)
    first = fixture.start('terminated', track)
    session, record = fixture.ready('terminated', track, first)
    try:
        os.killpg(first.pid, signal.SIGTERM)
    except PermissionError:
        pytest.skip('INCONCLUSIVE: sandbox denied TERM to fixture-owned process group')
    assert first.wait(timeout=5) != 0
    finished = wait_for(lambda: fixture.records(session, 'done'))
    assert finished[0]['child_reaped'] is True
    try:
        wait_for(lambda: gone(record['pid']) and gone(record['child']))
    except PermissionError:
        pytest.skip('INCONCLUSIVE: sandbox denied fixture-owned PID liveness query')
    replacement = fixture.start('after_term', track)
    fixture.ready('after_term', track, replacement)
    print('TERM root=' + str(first.pid), 'owned_children=0', 'lock_reacquired=True', flush=True)


@pytest.mark.parametrize('tool_rc,expected,message', [(75, 2, '같은 호스트 레인 실행 중 — 시작 안 함'),
                                                    (74, 4, '잠금 오류')])
def test_lock_tool_error_mapping_before_preflight(fixture, tool_rc, expected, message):
    # Only these mapping cases use a stub; contention/lifetime cases above use native tools.
    (fixture.base / 'bin/flock').unlink(missing_ok=True)
    fixture.put('bin/flock', '#!/bin/bash\nexit ' + str(tool_rc) + '\n', True)
    proc = fixture.start('error', 'kmmlu')
    assert proc.wait(timeout=5) == expected
    assert 'fixture kmmlu: ' + message in fixture.output('error')
    assert not (fixture.base / 'preflights').exists()
    assert not list((fixture.base / 'records').iterdir())


@pytest.mark.parametrize('track', TRACKS)
def test_dry_run_does_not_source_or_create_lock(fixture, track):
    fixture.put('shared/harness/harness_lib.sh', 'echo sourced > "$MODEL_TEST_BASE/sourced"\nreturn 4\n')
    proc = fixture.start('dry', track, dry=True)
    assert proc.wait(timeout=5) == 0
    assert not (fixture.base / 'sourced').exists()
    assert not (fixture.base / 'logs').exists()
    assert not (fixture.base / 'preflights').exists()


def test_lock_file_open_failure_is_rc4_before_preflight(fixture):
    (fixture.base / 'logs/resume_orch/.lane_host_fixture.invalid_18023.lock').mkdir(parents=True)
    proc = fixture.start('open_error', 'kmmlu')
    assert proc.wait(timeout=5) == 4
    assert 'fixture kmmlu: 잠금 오류' in fixture.output('open_error')
    assert not (fixture.base / 'preflights').exists()


def test_ipv6_endpoint_lock_filename(fixture):
    native(fixture)
    proc = fixture.start('ipv6', 'taubench_std4', '[::1]:18023')
    fixture.ready('ipv6', 'taubench_std4', proc)
    assert (fixture.base / 'logs/resume_orch/.lane_host____1__18023.lock').is_file()
