"""Hook phase traces prove dry-run and failure paths retain the common order."""
import pytest
import shlex

from orchestration.tests.laneconf_support import SAMPLE
from orchestration.tests.registry_support import RegistryComparison

HOOKS = '''
track_validate() { printf 'validate\\n' >> "$BASE/events"; }
track_export() {
  [ "$MODEL_TEST_BASE" = "$BASE" ] && [ -z "${MODEL:-}" ] || exit 91
  printf 'export\\n' >> "$BASE/events"
}
track_secrets() {
  [ "$OPENAI_API_KEY" = synthetic ] && [ "$(read_key FIXTURE_KEY)" = synthetic ] || exit 92
  [ -z "${MODEL:-}" ] || exit 93
  printf 'secrets\\n' >> "$BASE/events"
}
track_dry_run() {
  [ "$MODEL" = fixture_model ] || exit 94
  printf 'dry\\n' >> "$BASE/events"
}
track_pre_http() {
  [ "$MODEL" = fixture_model ] && [ "$HOST" = first ] || return 95
  printf 'pre_http\\n' >> "$BASE/events"
  return "${PRE_HTTP_RC:-0}"
}
track_run() { printf 'run\\n' >> "$BASE/events"; }
'''


def order_fixture(base):
    fx = RegistryComparison(base)
    fx.put('orchestration/tracks/order.sh', HOOKS)
    (fx.orch / 'lanes/order.sh').symlink_to('../run_lane.sh')
    fx.put('orchestration/models/sample.conf', SAMPLE + 'SESSION_ORDER=trace\n')
    activate = fx.base / '.venv/bin/activate'
    activate.write_text(activate.read_text() + 'printf "activate\\n" >> "$BASE/events"\n')
    fx.put('bin/python', '#!/bin/bash\nprintf "loader\\n" >> "$MODEL_TEST_BASE/events"\n'
           'printf "export MODEL=fixture_model\\nexport BASE_URL_V1=%s\\nexport BASE_URL_CHAT=%s\\n" '
           '"$BASE_URL_V1_OVERRIDE" "$BASE_URL_CHAT_OVERRIDE"\n', True)
    fx.put('shared/harness/harness_lib.sh', 'harness_lock() { printf "lock\\n" >> "$BASE/events"; '
           'return "${LOCK_RC:-0}"; }\n')
    fx.put('bin/curl', '#!/bin/bash\nprintf "http\\n" >> "$MODEL_TEST_BASE/events"\n'
           'while [ "$#" -gt 0 ]; do\n'
           'if [ "$1" = -o ]; then printf \'{"data":[{"id":"fixture_model"}]}\' > "$2"; shift 2; '
           'else shift; fi\ndone\nprintf 200\n', True)
    fx.put('bin/grep', '#!/bin/bash\nfor arg in "$@"; do\n'
           'case "$arg" in */.env) printf "dotenv\\n" >> ' + shlex.quote(str(fx.base / 'env_reads')) +
           ' ;; esac\ndone\nexec /usr/bin/grep "$@"\n', True)
    fx.env['PATH'] = str(fx.base / 'bin') + ':/usr/bin:/bin'
    return fx


@pytest.mark.parametrize('dry,lock_rc,pre_rc,rc,tail', [
    (True, 0, 0, 0, ['loader', 'dry']),
    (False, 0, 0, 0, ['secrets', 'loader', 'lock', 'pre_http', 'http', 'run']),
    (False, 3, 0, 2, ['secrets', 'loader', 'lock']),
    (False, 4, 0, 4, ['secrets', 'loader', 'lock']),
    (False, 0, 7, 7, ['secrets', 'loader', 'lock', 'pre_http']),
])
def test_registry_hook_order_and_failure_gates(tmp_path, dry, lock_rc, pre_rc, rc, tail):
    fx = order_fixture(tmp_path / 'checkout')
    if dry:
        (fx.base / '.env').unlink()
    result = fx.lane('sample', 'order', {'LANE_DRY_RUN': '1' if dry else '0',
                                        'LOCK_RC': str(lock_rc), 'PRE_HTTP_RC': str(pre_rc)})
    assert result.returncode == rc, result.stderr
    assert (fx.base / 'events').read_text().splitlines() == ['validate', 'activate', 'export', *tail]
    if dry:
        fx.assert_dry()
        assert not (fx.base / 'env_reads').exists()
    else:
        assert (fx.base / 'env_reads').read_text().splitlines() == ['dotenv', 'dotenv']


@pytest.mark.parametrize('missing', ['track_run', 'track_dry_run'])
@pytest.mark.parametrize('dry', [False, True])
def test_ch1_ch2_missing_hook_stops_before_all_events(tmp_path, missing, dry):
    fx = order_fixture(tmp_path / 'checkout')
    track = fx.orch / 'tracks/order.sh'
    track.write_text(HOOKS.replace(missing + '()', 'unused_hook()'))
    result = fx.lane('sample', 'order', {'LANE_DRY_RUN': '1' if dry else '0'})
    assert (result.returncode, result.stdout, result.stderr) == (
        2, b'', f'run_lane: track order defines no {missing}\n'.encode())
    for name in ('events', 'env_reads', 'logs', 'loader_inputs'):
        assert not (fx.base / name).exists(), name


def test_ch3_exported_function_cannot_hide_missing_hook(tmp_path):
    fx = order_fixture(tmp_path / 'checkout')
    (fx.orch / 'tracks/order.sh').write_text(HOOKS.replace('track_run()', 'unused_hook()'))
    parent = ('track_run() { printf inherited; }; export -f track_run; '
              '[ "$(/bin/bash -c track_run)" = inherited ] || exit 99; '
              'exec /bin/bash "$1" sample')
    result = fx.run(['/bin/bash', '-c', parent, 'parent', str(fx.orch / 'lanes/order.sh')],
                    {'LANE_DRY_RUN': '1'})
    assert result.returncode == 2, result.stderr
    assert result.stderr == b'run_lane: track order defines no track_run\n'
    assert not (fx.base / 'events').exists()
