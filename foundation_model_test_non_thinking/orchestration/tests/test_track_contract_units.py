"""CB4: static name membership; cannot prove assignment-before-read or eval targets."""
from pathlib import Path

import pytest

from orchestration.tests.track_contract import documented_inputs, unknown_inputs, variable_usage

ROOT = Path(__file__).resolve().parents[2]
TRACKS = ROOT / 'orchestration/tracks'


def test_cb4_all_tracks_obey_documented_inputs():
    allowed = documented_inputs((TRACKS / 'README.md').read_text())
    assert {'BASE', 'MODEL', 'SESSION', 'PYTHONPATH'} <= allowed
    for path in TRACKS.glob('*.sh'):
        assert not unknown_inputs(path.read_text(), allowed), (path.name, unknown_inputs(path.read_text(), allowed))
        assert '# Inputs' in path.read_text()


def test_cb4_negative_copy_rejects_undocumented_global(tmp_path):
    source = (TRACKS / 'kmmlu.sh').read_text()
    path = tmp_path / 'kmmlu.sh'
    path.write_text(source + '\ntrack_run() { printf "%s\\n" "$UNREGISTERED_INPUT"; }\n')
    allowed = documented_inputs((TRACKS / 'README.md').read_text())
    assert unknown_inputs(path.read_text(), allowed) == {'UNREGISTERED_INPUT'}
    with pytest.raises(AssertionError):
        assert not unknown_inputs(path.read_text(), allowed)


def test_scanner_ignores_quoted_assignments_and_local_work_variables():
    reads, writes = variable_usage('N=1; local RD=x; echo "MODEL=$MODEL ${RD} $((N + OFFSET))"')
    assert writes == {'N', 'RD'}
    assert {'MODEL', 'RD', 'N', 'OFFSET'} <= reads
    assert unknown_inputs('echo "MODEL=$MODEL"', set()) == {'MODEL'}
    assert unknown_inputs("echo '$LITERAL' # $COMMENT\n", set()) == set()
