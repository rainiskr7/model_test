"""CLI output/rc and write ordering from original synthetic derivations."""
import contextlib
import io
from pathlib import Path
from unittest.mock import patch
import pytest
import derive_multimodal_publish as cli


def _run_case(case):
    path = Path('/synthetic/sidecar.json')
    sidecar = {'status': 'LEGACY_REVALIDATED', 'counts': {'attempted': 2, 'errored': 0, 'unresolved': 0}}
    args = ['--base', '/synthetic']
    calls = []
    if case != 'all':
        args += ['--source', '/synthetic/source']
    if case in ('write', 'race', 'native', 'reject', 'preflight_bad'):
        args += ['--write']
    if case == 'native':
        args += ['--native']
    if case == 'reject':
        args += ['--reject-reason', 'runner failed']
    if case in ('preflight_ok', 'preflight_bad'):
        args += ['--preflight-kreta']
    existing = {'status': 'NATIVE'} if case == 'skip' else None
    output, errors = io.StringIO(), io.StringIO()
    with patch.object(cli, 'derived_sidecar_path', return_value=path), \
         patch.object(Path, 'exists', return_value=True), \
         patch.object(cli, 'inspect_native_sidecar', return_value=(existing, None)), \
         patch.object(cli, 'derive_source', return_value=(path, sidecar), side_effect=ValueError('broken') if case == 'error' else None), \
         patch.object(cli, 'native_sidecar_from_source', return_value=(path, sidecar)), \
         patch.object(cli, 'rejected_sidecar_from_source', return_value=(path, sidecar)), \
         patch.object(cli, 'migrate_stale_native', return_value=None), \
         patch.object(cli, 'derive_all', return_value=[(path, sidecar)]), \
         patch.object(cli, 'preflight_kreta_source', return_value=(case == 'preflight_ok', ['invalid row'])), \
         patch.object(cli, 'write_sidecar', side_effect=lambda *args: calls.append('write')), \
         patch.object(cli, 'write_legacy_sidecar', side_effect=lambda *args, **kwargs: (calls.append('legacy') or (case != 'race', None))), \
         contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        rc = cli.main(args)
    return rc, output.getvalue(), errors.getvalue(), calls


@pytest.mark.parametrize('case', ['all', 'single', 'write', 'race', 'skip', 'native', 'reject', 'error', 'preflight_ok', 'preflight_bad'])
def test_cli_matches_original_return_output_and_writes(case):
    assert _run_case(case) == EXPECTED_CASES[case]


def test_record_native_skip_mutates_only_supplied_list():
    paths = [Path('first')]
    cli._record_native_skip(Path('second'), {}, out=paths)
    assert paths == [Path('first'), Path('second')]


def test_parse_args_preserves_incompatible_option_error(capsys):
    with pytest.raises(SystemExit) as error:
        cli._parse_args(['--source', '/synthetic/source', '--native', '--reject-reason', 'failed'])
    assert error.value.code == 2
    assert '--reject-reason cannot be combined with --native/--preflight-kreta' in capsys.readouterr().err


# Captured from the unmodified A2 input using the synthetic cases above.
EXPECTED_CASES = {'all': (0,
         'would write /synthetic/sidecar.json: LEGACY_REVALIDATED (attempted=2, errored=0, '
         'unresolved=0)\n'
         '1 sidecar(s); dry-run; native skipped=0\n',
         '',
         []),
 'single': (0,
            'would write /synthetic/sidecar.json: LEGACY_REVALIDATED (attempted=2, errored=0, '
            'unresolved=0)\n'
            '1 sidecar(s); dry-run; native skipped=0\n',
            '',
            []),
 'write': (0,
           'wrote /synthetic/sidecar.json: LEGACY_REVALIDATED (attempted=2, errored=0, '
           'unresolved=0)\n'
           '1 sidecar(s); write complete; native skipped=0\n',
           '',
           ['legacy']),
 'race': (0,
          'skipped existing NATIVE /synthetic/sidecar.json\n'
          'skipped 1 existing NATIVE sidecar(s)\n'
          '0 sidecar(s); write complete; native skipped=1\n',
          '',
          ['legacy']),
 'skip': (0,
          'skipped existing NATIVE /synthetic/sidecar.json\n'
          'skipped 1 existing NATIVE sidecar(s)\n'
          '0 sidecar(s); dry-run; native skipped=1\n',
          '',
          []),
 'native': (1,
            'wrote /synthetic/sidecar.json: LEGACY_REVALIDATED (attempted=2, errored=0, '
            'unresolved=0)\n'
            '1 sidecar(s); write complete; native skipped=0\n',
            '',
            ['write']),
 'reject': (0,
            'wrote /synthetic/sidecar.json: LEGACY_REVALIDATED (attempted=2, errored=0, '
            'unresolved=0)\n'
            '1 sidecar(s); write complete; native skipped=0\n',
            '',
            ['write']),
 'error': (2, '', 'derive failed: broken\n', []),
 'preflight_ok': (0, 'KRETA preflight OK: /synthetic/source\n', '', []),
 'preflight_bad': (1, '', 'KRETA preflight REJECTED: invalid row\n', ['write'])}
