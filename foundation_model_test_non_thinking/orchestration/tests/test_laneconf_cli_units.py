"""CLI byte errors and quoting are checked against the pre-change lane entry."""
import pytest

from orchestration.tests.laneconf_support import Comparison, SAMPLE, assignments


@pytest.mark.parametrize('text,message', [
    ('no_equals', 'expected key=value: no_equals'),
    (' # comment', 'expected key=value:  # comment'),
    (' \t', 'expected key=value:  \t'),
    (SAMPLE + 'UNKNOWN=x\n', 'unknown key: UNKNOWN'),
    (SAMPLE + 'FULL_UNKNOWN=x\n', 'unknown key: UNKNOWN'),
    (SAMPLE + 'FULL_DISPLAY=x\n', 'key cannot have track prefix: DISPLAY'),
    (SAMPLE + 'FULL_SESSION_KMMLU=x\n', 'key cannot have track prefix: SESSION_KMMLU'),
    (SAMPLE + ' REPS=2\n', 'unknown key:  REPS'),
    (SAMPLE + 'REPS =2\n', 'unknown key: REPS '),
    (SAMPLE.replace('CONFIG=qwen_qwen3.5_27b_fp8', 'CONFIG='), 'required key: CONFIG'),
    (SAMPLE.replace('DISPLAY=fixture', 'DISPLAY='), 'required key: DISPLAY'),
    (SAMPLE.replace('SESSION_KMMLU=fixture', 'SESSION_KMMLU='), 'required key: SESSION_KMMLU'),
    (SAMPLE.replace('KEYVAR=FIXTURE_KEY', 'KEYVAR=1KEY'), 'invalid environment variable name'),
])
def test_error_bytes_match_original_shell(tmp_path, text, message):
    fx = Comparison(tmp_path / 'checkout')
    fx.put('orchestration/models/sample.conf', text)
    expected = ('run_lane: ' + message + '\n').encode()
    for side in ('HEAD', 'working'):
        fx.install(side)
        result = fx.lane('sample')
        assert (result.returncode, result.stdout, result.stderr) == (2, b'', expected)
    cli = fx.cli('sample')
    assert (cli.returncode, cli.stdout, cli.stderr) == (2, b'', expected)


def test_cli_no_export_roundtrip_literal_and_unselected_duplicate(tmp_path):
    fx = Comparison(tmp_path / 'checkout')
    literal = 'a\'b "c" $(touch unexpected) `echo bad` = d'
    fx.put('orchestration/models/sample.conf', SAMPLE.replace('LANE_TOKENIZER=unused',
                                                            'LANE_TOKENIZER=' + literal))
    cli = fx.cli('sample')
    assert assignments(cli)['LANE_TOKENIZER'] == literal
    assert b'export ' not in cli.stdout
    result = fx.lane('sample')
    assert result.returncode == 0, result.stderr
    assert literal.encode() in result.stdout
    assert not (fx.base / 'unexpected').exists()
    fx.put('orchestration/models/sample.conf', SAMPLE + 'FULL_REPS=1\nFULL_REPS=2\n')
    result = fx.lane('sample', 'kmmlu')
    assert (result.returncode, result.stdout, result.stderr) == (
        2, b'', b'run_lane: duplicate key: FULL_REPS\n')
    fx.assert_dry()
