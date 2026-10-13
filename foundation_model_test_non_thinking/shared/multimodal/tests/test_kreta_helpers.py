"""CLI parity with the heredocs last present in 3822748.

Parity = same rc, same stdout, and the same final stderr line (the exception type and
message). Traceback frames differ by construction once the code lives in a file
instead of stdin, and pinning them would only force wrapper hacks into the helpers.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from shared.multimodal.benches.metadata import build_resume_context

REPO = Path(__file__).resolve().parents[3]
BENCHES = REPO / 'shared/multimodal/benches'
HEREDOC_COMMIT = '3822748'
SHELLS = ('run_koffvqa', 'run_kreta', 'run_kreta_resume')


@pytest.fixture(scope='module')
def head_heredocs():
    prefix = subprocess.run(['git', 'rev-parse', '--show-prefix'], cwd=REPO,
                            text=True, capture_output=True, check=True).stdout.strip()
    bodies = {}
    for shell in SHELLS:
        shown = subprocess.run(['git', 'show', f'{HEREDOC_COMMIT}:{prefix}shared/multimodal/{shell}.sh'],
                               cwd=REPO, text=True, capture_output=True, check=False)
        if shown.returncode:
            pytest.skip(f'oracle commit {HEREDOC_COMMIT} unavailable: {shown.stderr.strip()[:120]}')
        original = shown.stdout.splitlines(keepends=True)
        for name, marker in [('paths', 'SAFE_MODEL='), ('context', 'python - "$SCRIPT_DIR/benches"'),
                             ('output', 'python - "$OUT"')]:
            starts = [i for i, line in enumerate(original) if marker in line]
            if not starts:
                assert shell == 'run_koffvqa' and name != 'paths'
                continue
            start = starts[0] + 1
            terminator = 'PYEOF' if "<<'PYEOF'" in original[start - 1] else 'PY'
            stop = next(i for i in range(start, len(original)) if original[i].strip() == terminator)
            bodies[shell, name] = ''.join(original[start:stop])
    return bodies


def run_python(args, *, source=None, cwd=REPO):
    result = subprocess.run([sys.executable, *map(str, args)],
                            input=source.encode() if source is not None else None,
                            cwd=cwd, capture_output=True, check=False)
    return result.returncode, result.stdout, result.stderr


def parity(result):
    """(rc, stdout, last stderr line) — the part of an error that callers and humans read."""
    rc, out, err = result
    tail = [line for line in err.splitlines() if line.strip()]
    return rc, out, (tail[-1] if tail else b'')


@pytest.mark.parametrize('shell', SHELLS)
@pytest.mark.parametrize('error', [False, True], ids=['normal', 'error'])
def test_safe_model(tmp_path, head_heredocs, shell, error):
    (tmp_path / 'results/Model_A').mkdir(parents=True)
    # A bad benches argument tests an uncaught import error on every filesystem.
    benches = tmp_path / 'missing-benches' if error else BENCHES
    args = [benches, tmp_path, 'model/a']
    line = next(line for line in (REPO / f'shared/multimodal/{shell}.sh').read_text().splitlines()
                if line.startswith('SAFE_MODEL='))
    source = line.split("-c '", 1)[1].split("'", 1)[0]
    actual = run_python(['-c', source, *args])
    assert parity(actual) == parity(run_python(['-', *args], source=head_heredocs[shell, 'paths']))
    assert actual[0] == (1 if error else 0)
    if not error:
        assert actual == (0, b'Model_A\n', b'')


@pytest.mark.parametrize('shell,helper', [
    ('run_kreta', 'kreta_resume_context'),
    ('run_kreta_resume', 'kreta_resume_context_check'),
])
@pytest.mark.parametrize('case', ['normal', 'invalid-config', 'stale-context', 'invalid-context'])
def test_context(tmp_path, head_heredocs, shell, helper, case):
    config = {'model': {'name': '한글-model'}, 'decoding': {'max_tokens': 32}}
    config_path = tmp_path / 'config.json'
    config_path.write_text('{' if case == 'invalid-config' else json.dumps(config))
    context_path = tmp_path / 'context.json'
    context = build_resume_context(config, setting='direct', session='session')
    context_path.write_text('{' if case == 'invalid-context' else json.dumps({} if case == 'stale-context' else context))
    before = context_path.read_bytes()
    args = [BENCHES, config_path, context_path, 'direct', 'session']
    actual = run_python([BENCHES / f'{helper}.py', *args])
    actual_file = context_path.read_bytes()
    context_path.write_bytes(before)
    expected = run_python(['-', *args], source=head_heredocs[shell, 'context'])
    assert parity(actual) == parity(expected)
    assert actual_file == context_path.read_bytes()
    error = case == 'invalid-config' or (shell.endswith('_resume') and case != 'normal')
    assert actual[0] == (1 if error else 0)
    if not error:
        assert actual == (0, b'', b'')
        assert json.loads(actual_file) == context


@pytest.mark.parametrize('shell', ['run_kreta', 'run_kreta_resume'])
@pytest.mark.parametrize('error', [False, True], ids=['normal', 'error'])
def test_output_check(tmp_path, head_heredocs, shell, error):
    # Substitute upstream evaluate only; no real benchmark repository is opened.
    (tmp_path / 'evaluate.py').write_text(
        'def check_files(folder):\n    print("검사:", folder)\n'
        + ('    raise ValueError("평가 오류")\n' if error else ''))
    args = [tmp_path / 'output']
    actual = run_python([BENCHES / 'kreta_output_check.py', *args], cwd=tmp_path)
    assert parity(actual) == parity(run_python(['-', *args], source=head_heredocs[shell, 'output'], cwd=tmp_path))
    assert actual[0] == (1 if error else 0)
