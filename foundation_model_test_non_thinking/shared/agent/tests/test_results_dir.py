"""Result spelling contracts; fixture-only evaluation, no credentials or network."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import types

import pytest

from _agent_fakes import load_runner

BASE = Path(__file__).resolve().parents[3]
CUSTOM = BASE / 'shared/agent/gpustack_custom'
SHELL = BASE / 'shared/results_dir.sh'


def shell_result(base, name, env=None):
    return subprocess.run(
        ['/bin/bash', '-c', 'source "$1"; results_model_dir "$2" "$3"',
         'test', str(SHELL), str(base), name],
        text=True, capture_output=True, env=env,
    )


def duplicate_listing(monkeypatch, root, names=('model_x', 'Model_X')):
    """Simulate distinct directories even on a case-insensitive filesystem."""
    original = Path.iterdir
    entries = [types.SimpleNamespace(name=n, is_dir=lambda: True) for n in names]
    monkeypatch.setattr(Path, 'iterdir', lambda self: iter(entries) if self == root else original(self))


@pytest.mark.parametrize('module_name,function,track', [
    ('shared.taubench.scoring.score_run', '_results_dir', 'taubench'),
    ('shared.agent.scoring.score_run', '_result_dir_from_args', 'agent'),
    ('shared.agent.scoring.validate_run', '_results_dir_from_args', 'agent'),
])
def test_scoring_cli_model_spelling(tmp_path, monkeypatch, module_name, function, track):
    monkeypatch.syspath_prepend(str(BASE))
    module = importlib.import_module(module_name)
    monkeypatch.setenv('MODEL_TEST_BASE', str(tmp_path))
    args = module.parse_args(['--model', 'model-x', '--timestamp', 'session'])
    (tmp_path / 'results/Model_X').mkdir(parents=True)
    expected = tmp_path / 'results/Model_X/session/language' / track
    assert getattr(module, function)(args) == expected
    duplicate_listing(monkeypatch, tmp_path / 'results')
    with pytest.raises(ValueError, match='case-fold ambiguous'):
        getattr(module, function)(args)
    # Actual CLI error handling must also retain rc 2, not score an arbitrary folder.
    assert module.main(['--model', 'model-x', '--timestamp', 'session']) == 2


@pytest.mark.parametrize('spelling,requested', [(None, 'model_x'), ('Model_X', 'model_x'), ('Straße', 'STRASSE')])
def test_shell_zero_one_and_unicode(tmp_path, spelling, requested):
    # An unrelated file must never count as a matching directory.
    if spelling is not None:
        (tmp_path / 'results' / spelling).mkdir(parents=True)
    result = shell_result(tmp_path, requested)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (spelling or requested)
    assert not (tmp_path / '.eval_session').exists()


def test_shell_empty_root_and_files(tmp_path):
    (tmp_path / 'results').mkdir()
    (tmp_path / 'results/MODEL_X').write_text('not a directory')
    result = shell_result(tmp_path, 'model_x')
    assert (result.returncode, result.stdout) == (0, 'model_x\n')


def test_shell_ambiguity_actual_inline_python(tmp_path):
    (tmp_path / 'results').mkdir()
    # Only filesystem enumeration is simulated; the shell and inline Python are real.
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    wrapper = bindir / 'python3'
    wrapper.write_text(f'''#!{sys.executable}
import sys
from pathlib import Path
from types import SimpleNamespace
sys.argv = sys.argv[1:]
root = Path(sys.argv[1]) / 'results'
original = Path.iterdir
Path.iterdir = lambda self: iter([SimpleNamespace(name=n, is_dir=lambda: True) for n in ('Model_X', 'model_x')]) if self == root else original(self)
exec(compile(sys.stdin.read(), '<results_dir.sh>', 'exec'))
''')
    wrapper.chmod(0o755)
    result = shell_result(tmp_path, 'model_x', dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH']))
    assert result.returncode == 2
    assert not result.stdout
    assert 'case-fold ambiguous' in result.stderr
    assert not list((tmp_path / 'results').iterdir())


def test_runner_cli_ambiguity_before_session_or_evaluation(tmp_path):
    (tmp_path / 'results/Model_X').mkdir(parents=True)
    # Use a subprocess to verify the real CLI exit status, including sys.exit(2).
    code = '''import sys
from pathlib import Path
import pytest
sys.path.insert(0, sys.argv[1])
from test_results_dir import load_runner, duplicate_listing
base = Path(sys.argv[2])
with pytest.MonkeyPatch.context() as mp:
    mp.setenv('MODEL_TEST_BASE', str(base))
    mp.delenv('EVAL_TIMESTAMP', raising=False)
    module = load_runner(mp, base)
    duplicate_listing(mp, base / 'results')
    sys.argv = ['runner', '--model', 'model-x', '--timeout', '2', '--request-timeout', '1']
    sys.exit(module.main())
'''
    result = subprocess.run([sys.executable, '-c', code, str(Path(__file__).parent), str(tmp_path)],
                            text=True, capture_output=True)
    assert result.returncode == 2, result.stdout + result.stderr
    assert 'case-fold ambiguous' in result.stderr
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*')) == ['results', 'results/Model_X']


@pytest.mark.parametrize('custom_root,local', [(False, False), (False, True), (True, False)])
def test_runner_single_spelling_reaches_real_save(tmp_path, monkeypatch, custom_root, local):
    monkeypatch.setenv('MODEL_TEST_BASE', str(tmp_path))
    monkeypatch.setenv('EVAL_TIMESTAMP', 'session')
    root = tmp_path / ('custom-output' if custom_root else 'results')
    (root / 'Model_X').mkdir(parents=True)
    module = load_runner(monkeypatch, tmp_path)
    original = module.resolve_results_model_dir
    calls = []

    def resolve(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(module, 'resolve_results_model_dir', resolve)
    if custom_root:
        module.run_benchmark_on_dataset('L1', [{'task_id': 'fixture'}], 'model-x', log_dir=str(root), run_timestamp='session')
    else:
        monkeypatch.setattr(sys, 'argv', ['runner', '--model', 'huggingface/model-x' if local else 'model-x',
                                        '--timeout', '2', '--request-timeout', '1'] + (['--use-local'] if local else []))
        module.main()
    assert len(calls) == 1  # main -> benchmark -> save carries the resolved spelling.
    output = root / 'Model_X/session/language/agent/L1.json'
    assert json.loads(output.read_text())['metadata']['model'] == 'model-x'
    assert [p.name for p in root.iterdir()] == ['Model_X']
    assert (tmp_path / 'evaluated').exists()


def test_runner_custom_log_dir_ambiguity_before_adapter(tmp_path, monkeypatch):
    root = tmp_path / 'custom-output'
    root.mkdir()
    module = load_runner(monkeypatch, tmp_path)
    duplicate_listing(monkeypatch, root)
    with pytest.raises(ValueError, match='case-fold ambiguous'):
        module.run_benchmark_on_dataset('L1', [{'task_id': 'fixture'}], 'model-x', log_dir=str(root))
    assert not (tmp_path / 'adapter_created').exists()
    assert not (tmp_path / 'evaluated').exists()
    assert not list(tmp_path.rglob('*.json'))


@pytest.mark.parametrize('resolution_fails', [False, True])
@pytest.mark.parametrize('scoring_rc', [1, 2])
def test_agent_shell_failure_message_preserves_scoring_rc(tmp_path, resolution_fails, scoring_rc):
    agent = tmp_path / 'shared/agent'
    custom = agent / 'gpustack_custom'
    custom.mkdir(parents=True)
    script = agent / 'run_gpustack_custom.sh'
    script.write_bytes((BASE / 'shared/agent/run_gpustack_custom.sh').read_bytes())
    koa = tmp_path / 'data/Ko-AgentBench'
    (koa / 'bench/adapters').mkdir(parents=True)
    for name in ('run_gpustack_benchmark_with_logging.py', 'runner_timeout_config.py',
                 'result_observability.py', 'openai_compat_adapter.py', 'tool_call_parser.py'):
        (custom / name).touch()
    (custom / 'run_ko-agentbench.sh').write_text('exit 0\n')
    helper = tmp_path / 'shared/results_dir.sh'
    if resolution_fails:
        helper.write_text('results_model_dir() { echo "ambiguous fixture" >&2; return 2; }\n')
    else:
        helper.write_bytes(SHELL.read_bytes())
    (tmp_path / 'results/Model_X').mkdir(parents=True)
    scorer = tmp_path / 'scorer'
    scorer.write_text(f'#!/bin/bash\nexit {scoring_rc}\n')
    scorer.chmod(0o755)
    result = subprocess.run(['/bin/bash', str(script), 'model-x'], text=True, capture_output=True,
                            env=dict(os.environ, MODEL_TEST_BASE=str(tmp_path), EVAL_TIMESTAMP='session', PY=str(scorer)))
    assert result.returncode == scoring_rc
    if resolution_fails:
        assert '결과 경로 철자를 해석하지 못했습니다' in result.stderr
    else:
        assert str(tmp_path / 'results/Model_X/session/language/agent') in result.stderr
