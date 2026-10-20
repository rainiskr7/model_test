"""CD2: literal standalone assignments only; see assignment_scan for limitations.

Command prefixes are intentional child environments, not internal names. Dynamic
eval/indirect destinations are not proven by this static check. Schema destinations
and resolved SESSION names are inspected separately, including a poisoned copy.
"""
import pytest

from orchestration.laneconf.schema import FORBIDDEN_VARIABLES, key_table
from orchestration.tests.assignment_scan import standalone_assignments
from orchestration.tests.laneconf_support import Comparison, REPO, SAMPLE, TRACKS, assignments


def test_cd2_schema_and_shell_names():
    names = {setting.variable for setting in key_table(TRACKS).values()} | {'SESSION'}
    common = standalone_assignments((REPO / 'orchestration/run_lane.sh').read_text())
    assert {'TRACK', 'HERE', 'BASE', 'LABEL', 'PREFIX', 'STOP_LABEL', 'END_LABEL',
            'MODEL_TEST_BASE', 'HOST', 'TOK', 'BASE_TS', 'ORCH', 'OPENAI_API_KEY'} <= common
    assert 'PYTHONPATH' not in common
    for path in [REPO / 'orchestration/run_lane.sh', *sorted((REPO / 'orchestration/tracks').glob('*.sh'))]:
        names |= standalone_assignments(path.read_text())
    assert not names & FORBIDDEN_VARIABLES


def test_cd2_poisoned_schema_copy_fails(tmp_path):
    fx = Comparison(tmp_path / 'checkout')
    fx.put('orchestration/models/sample.conf', SAMPLE)
    schema = fx.orch / 'laneconf/schema.py'
    schema.write_text(schema.read_text().replace('Setting("LANE_DISPLAY",', 'Setting("PATH",'))
    names = set(assignments(fx.cli('sample')))
    assert names & FORBIDDEN_VARIABLES == {'PATH'}
    with pytest.raises(AssertionError):
        assert not names & FORBIDDEN_VARIABLES


def test_cd2_scanner_boundaries_and_command_prefixes():
    source = '''A=1 B="two words"; export C=3
local D=4; readonly E=5 && F=6
PYTHONPATH=somewhere python -B -m example
echo HOME=x; env DISPLAY=x command
if true; then TERM=x; fi
'''
    assert standalone_assignments(source) == {'A', 'B', 'C', 'D', 'E', 'F', 'TERM'}
    for source in ('DISPLAY=x', 'true && HOME=x', 'local PATH=x', 'export LANG=x',
                   'HOME=$(cd "$(dirname "$0")" && pwd)', 'TERM=x # comment\necho ok'):
        assert standalone_assignments(source) & FORBIDDEN_VARIABLES
    assert not standalone_assignments('eval "DISPLAY=x"; read HOME; printf -v PATH x')
    assert standalone_assignments('VALUES=(one "two words"); VALUES+=(three)') == {'VALUES'}
    assert standalone_assignments('local_name=x HOME=y; local_name=x PATH=y command') == {'HOME'}


@pytest.mark.parametrize('key', ['DISPLAY', 'FULL_DISPLAY'])
def test_cd3_old_key_has_actionable_error(tmp_path, key):
    fx = Comparison(tmp_path / 'checkout')
    fx.put('orchestration/models/sample.conf', SAMPLE + key + '=old\n')
    expected = b'run_lane: key renamed: DISPLAY -> LANE_DISPLAY\n'
    for result in (fx.cli('sample'), fx.lane('sample')):
        assert (result.returncode, result.stdout, result.stderr) == (2, b'', expected)


def test_display_common_key_survives_lane_track_registration(tmp_path):
    fx = Comparison(tmp_path / 'checkout')
    fx.put('orchestration/tracks/lane.sh', '# registration fixture\n')
    # LANE_TOKENIZER already has a documented prefix collision; isolate the new key.
    fx.put('orchestration/models/sample.conf', SAMPLE.replace('LANE_TOKENIZER=unused\n', ''))
    assert assignments(fx.cli('sample'))['LANE_DISPLAY'] == 'fixture'


def test_cr1_operational_docs_use_absolute_lane_paths():
    for path in [REPO / 'README.md', *REPO.glob('orchestration/**/README*.md')]:
        assert 'bash orchestration/lanes/' not in path.read_text(), path


def test_baseline_key_adapter_preserves_value_cr_and_missing_lf(tmp_path):
    fx = Comparison(tmp_path / 'checkout')
    path = fx.orch / 'models/sample.conf'
    current = b'LANE_DISPLAY="DISPLAY LANE_DISPLAY"\r\nFULL_LANE_DISPLAY=x'
    historical = b'DISPLAY="DISPLAY LANE_DISPLAY"\r\nFULL_DISPLAY=x'
    path.write_bytes(current)
    fx.display_keys('HEAD')
    assert path.read_bytes() == historical
    fx.display_keys('working')
    assert path.read_bytes() == current
    fx.display_keys('working')
    assert path.read_bytes() == current
