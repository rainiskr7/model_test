"""Complete stdout contract for extracted agent table printers."""
import contextlib
import hashlib
import io
from shared.agent.scoring import score_run as scorer


def _summary():
    level = {'total': 2, 'score': None, 'unscorable_reason': 'empty', 'applied_metrics': 0, 'metrics': {}}
    version = {'by_level': {'L6': level, 'L4': {'score': 0.5}}, 'agent_score': None,
               'scored_levels': 0, 'required_levels': 6, 'agent_score_status': 'incomplete'}
    return {'model': 'm', 'track': 'agent', 'by_level': {'L4': level}, 'scoring_v3': version,
            'scoring_v4': version, 'cache_miss_diagnostics': {'by_level': {'L4': {'total_calls': 2, 'cache_misses': 1, 'miss_rate': 0.5}}}}


def _stdout(summary):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        scorer.print_table(summary, 2)
    return stream.getvalue()


def test_print_table_preserves_version_matrix_bytes():
    assert hashlib.sha256(_stdout(_summary()).encode()).hexdigest() == EXPECTED_STDOUT_HASH


def test_print_table_preserves_empty_defaults():
    assert hashlib.sha256(_stdout({'model': 'm', 'track': 'agent', 'by_level': {}}).encode()).hexdigest() == EXPECTED_EMPTY_HASH


# Captured from the unmodified A2 input using the synthetic cases above.
EXPECTED_STDOUT_HASH = '00ed314efbc7690aae10e44896186981a8902997aaf43133cc8c7b72c1b1163c'
EXPECTED_EMPTY_HASH = '1179f25e58ac2b500ef3b63a8cef29f0f8fab00a18e85cb61e7a76c7e12d0b54'
