"""CS1: owned BASE lifecycle, failure evidence, interruption, and symlink safety."""
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from orchestration.laneconf import ConfigError
from orchestration.smoke import cleanup, execution, http_preflight, isolation, main, offline_checks, processes
from orchestration.smoke.memory_transport import response
from orchestration.smoke.offline_checks import fixture
from orchestration.smoke.offline_server import start

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def owned_base(tmp_path):
    root = tmp_path / 'code'
    root.mkdir()
    base = isolation.assemble(root)
    try:
        yield root, base
    finally:
        if base.exists():
            cleanup.remove_base(base, root, created=base)


@pytest.mark.parametrize('rc,keep,kept', [(0, False, False), (0, True, True),
    (1, False, True), (77, False, True), (130, False, True), (2, False, False)])
def test_cs1_verdict_retention(owned_base, rc, keep, kept):
    root, base = owned_base
    summary = cleanup.finish(dict(rc=rc, base=str(base)), root, base, keep)
    assert summary['rc'] == rc
    assert summary['base_kept'] is kept and base.exists() is kept


def test_cleanup_unlinks_inputs_without_following_them(owned_base):
    root, base = owned_base
    for name in ('data', 'configs', 'shared', '.venv'):
        (root / name).mkdir()
        (root / name / 'untouched').write_bytes(b'input')
        if not (base / name).is_symlink():
            (base / name).symlink_to(root / name, target_is_directory=True)
    cleanup.remove_base(base, root, created=base)
    assert not base.exists()
    for name in ('data', 'configs', 'shared', '.venv'):
        assert (root / name / 'untouched').read_bytes() == b'input'


def test_cleanup_rejects_unowned_wrong_parent_link_and_inside_root(owned_base, tmp_path):
    root, base = owned_base
    wrong = tmp_path / 'serving-smoke-fake'
    wrong.mkdir()
    link = base.parent / (base.name + '-link')
    link.symlink_to(base, target_is_directory=True)
    try:
        for candidate, owner, code in [(base, wrong, root), (wrong, wrong, root),
                                       (link, link, root), (base, base, base)]:
            with pytest.raises(ValueError):
                cleanup.remove_base(candidate, code, created=owner)
        assert base.exists() and wrong.exists()
    finally:
        link.unlink()


def test_cleanup_failure_keeps_verdict_and_reports_error(owned_base, monkeypatch):
    root, base = owned_base
    with monkeypatch.context() as patch:
        patch.setattr(cleanup.shutil, 'rmtree', Mock(side_effect=PermissionError('fixture denial')))
        summary = cleanup.finish(dict(rc=0), root, base)
    assert summary == dict(rc=0, base_kept=True, cleanup_error='fixture denial')
    assert base.exists()


@pytest.mark.parametrize('error', [OSError('construction failed'), KeyboardInterrupt()])
def test_assemble_partial_failure_removes_only_its_directory(tmp_path, monkeypatch, error):
    created = []
    mkdtemp = isolation.tempfile.mkdtemp
    def allocate(**kwargs):
        path = mkdtemp(**kwargs)
        created.append(Path(path).resolve())
        return path
    monkeypatch.setattr(isolation.tempfile, 'mkdtemp', allocate)
    monkeypatch.setattr(Path, 'symlink_to', Mock(side_effect=error))
    with pytest.raises(type(error)):
        isolation.assemble(tmp_path)
    assert len(created) == 1 and not created[0].exists()


@pytest.mark.parametrize('error,rc,kept', [(ConfigError('bad fixture'), 2, False),
    (KeyboardInterrupt(), 130, True), (OSError('missing fixture'), 77, True)])
def test_main_pretrack_failures_and_interrupt(owned_base, monkeypatch, error, rc, kept):
    root, base = owned_base
    monkeypatch.setattr(main, 'assemble', lambda root: base)
    monkeypatch.setattr(main, 'configuration', Mock(side_effect=error))
    summary = main.execute_smoke(root, SimpleNamespace(model_conf='fixture', tracks=[], keep=False))
    assert summary['rc'] == rc and summary['base_kept'] is kept
    assert base.exists() is kept


@pytest.mark.parametrize('interrupted', [True, False])
def test_interrupt_and_timeout_terminate_and_reap_child_group(tmp_path, monkeypatch, interrupted):
    error = KeyboardInterrupt() if interrupted else subprocess.TimeoutExpired('fixture', 1)
    child = SimpleNamespace(pid=123456, returncode=-15,
                            communicate=Mock(side_effect=[error, ('stopped', None)]))
    monkeypatch.setattr(execution.subprocess, 'Popen', Mock(return_value=child))
    kill = Mock()
    monkeypatch.setattr(processes.os, 'killpg', kill)
    ctx = SimpleNamespace(base=tmp_path, env={'OPENAI_API_KEY': 'synthetic'}, stamp='fixture')
    (tmp_path / 'logs/smoke/fixture').mkdir(parents=True)
    result = {'timeout': False}
    with pytest.raises(KeyboardInterrupt if interrupted else ValueError):
        execution.invoke(ctx, 'nlu', ['fixture'], result)
    assert child.communicate.call_count == 2
    kill.assert_called_once_with(child.pid, processes.signal.SIGTERM)
    if not interrupted:
        assert result['timeout'] and result['runner_rc'] == -15


def test_terminate_escalates_and_reaps(monkeypatch):
    child = SimpleNamespace(pid=123456, communicate=Mock(side_effect=[
        subprocess.TimeoutExpired('fixture', 3), ('killed', None)]))
    kill = Mock()
    monkeypatch.setattr(processes.os, 'killpg', kill)
    assert processes.terminate(child) == ('killed', None)
    assert [call.args for call in kill.call_args_list] == [
        (child.pid, processes.signal.SIGTERM), (child.pid, processes.signal.SIGKILL)]
    assert child.communicate.call_count == 2


@pytest.mark.parametrize('fail', [False, True])
def test_offline_exercise_retains_all_bases_until_checks_finish(tmp_path, monkeypatch, fail):
    owned = []
    def cases(root, server, stack):
        for _ in range(2):
            base = isolation.assemble(root)
            owned.append(base)
            stack.callback(cleanup.remove_base, base, root, created=base)
        assert all(base.exists() for base in owned)
        if fail:
            raise ValueError('fixture assertion failed')
        return [dict(base=str(base)) for base in owned]
    monkeypatch.setattr(offline_checks, 'exercise_cases', cases)
    if fail:
        with pytest.raises(ValueError, match='fixture assertion'):
            offline_checks.exercise(tmp_path, None)
    else:
        assert all(not row['base_kept'] for row in offline_checks.exercise(tmp_path, None))
    assert len(owned) == 2 and not any(base.exists() for base in owned)


@pytest.mark.parametrize('fault,keep,rc,kept', [(False, False, 0, False),
    (True, False, 1, True), (False, True, 0, True)])
def test_cs1_memory_transport_cli(tmp_path, monkeypatch, capsys, fault, keep, rc, kept):
    """Exercise real CLI/configuration/runner logic without claiming HTTP integration."""
    with fixture(ROOT, '127.0.0.1:1') as root:
        monkeypatch.setenv('SMOKE_FIXTURE_HOST', '127.0.0.1:1')
        state = SimpleNamespace(track='harness', model='qwen_qwen3.5_27b_fp8', calls=[],
                                fault=('harness', 'models') if fault else None)
        monkeypatch.setattr(http_preflight, 'request', lambda ctx, path, payload=None:
                            response(state, 'models' if payload is None else 'chat'))
        output = tmp_path / 'summary.json'
        monkeypatch.setattr(main, '__file__', str(root / 'orchestration/smoke/main.py'))
        monkeypatch.setattr(main.sys, 'argv', ['smoke', 'fixture', 'harness', '--out', str(output)] +
                            (['--keep'] if keep else []))
        result = main.main()
        summary = json.loads(capsys.readouterr().out)
        base = Path(summary['base'])
        try:
            assert result == rc and summary == json.loads(output.read_text())
            assert summary['base_kept'] is kept and base.exists() is kept
            assert state.calls
        finally:
            if base.exists():
                cleanup.remove_base(base, root, created=base)


@pytest.mark.parametrize('fault,keep,rc,kept', [(False, False, 0, False),
    (True, False, 1, True), (False, True, 0, True)])
def test_cs1_cli_against_fake_server(tmp_path, monkeypatch, fault, keep, rc, kept):
    try:
        server, thread = start('qwen_qwen3.5_27b_fp8', 'synthetic-smoke-key')
    except PermissionError as exc:
        pytest.skip(f'INCONCLUSIVE loopback bind: {exc}')
    try:
        host = f'127.0.0.1:{server.server_port}'
        with fixture(ROOT, host) as root:
            monkeypatch.setenv('SMOKE_FIXTURE_HOST', host)
            server.track = 'harness'
            server.fault = ('harness', 'models') if fault else None
            shutil.copytree(ROOT / 'orchestration/smoke', root / 'orchestration/smoke',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            output = tmp_path / 'summary.json'
            argv = ['bash', str(root / 'orchestration/smoke/run_smoke.sh'), 'fixture',
                    'harness', '--out', str(output)] + (['--keep'] if keep else [])
            proc = subprocess.run(argv, cwd=tmp_path, capture_output=True, text=True, timeout=30)
            summary = json.loads(proc.stdout)
            base = Path(summary['base'])
            try:
                assert proc.returncode == rc, proc.stderr
                assert summary == json.loads(output.read_text())
                assert summary['base_kept'] is kept and base.exists() is kept
                assert server.calls
            finally:
                if base.exists():
                    cleanup.remove_base(base, root, created=base)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
