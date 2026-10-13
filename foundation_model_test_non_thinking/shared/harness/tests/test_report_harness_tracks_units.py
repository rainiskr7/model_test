"""Protocol partitioning and complete report bytes without real artifacts."""
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from reports import report_harness_tracks as report


def _summaries():
    return [{
        'model': name, 'session': 's', 'source_path': name,
        'publish_status': {'publishable': valid, 'warnings': ['unknown seed'], 'failures': ['incomplete']},
        'protocol': {'chat_template_applied': applied},
        'macro': {'accuracy': score, 'stderr': None, 'subjects': 1},
        'micro': {'accuracy': score, 'stderr': 0.01, 'items': 1234},
        'coverage': {'expected_subjects': 2, 'measured_subjects': 1},
        'by_subject': [{'task': 'a', 'accuracy': score}],
    } for name, valid, applied, score in [
        ('main', True, [True], 0.5), ('raw', True, [False], 0.8), ('bad', False, [], None)]]


def _render():
    scorer = SimpleNamespace(expected_tasks=lambda: ['a', 'missing'])
    with patch.object(report, '_claims', return_value=(
        {'main': {'claim_class': 'snapshot', 'k': 1, 'reason': 'synthetic'}},
        [('main', 'raw', {'comparable': False, 'reason': 'different'})],
    )):
        return report.render_markdown(_summaries(), [{'source_path': 'folded'}], scorer, Path('/synthetic'))


def test_chat_applied_requires_explicit_single_true():
    assert report._chat_applied({'protocol': {'chat_template_applied': [True]}}) is True
    assert report._chat_applied({'protocol': {'chat_template_applied': [True, False]}}) is False


def test_partition_protocols_preserves_score_order_and_empty_groups():
    ordered, other = report._partition_protocols(_summaries()[:2])
    assert [row['model'] for row in ordered] == ['main']
    assert [row['model'] for row in other] == ['raw']
    assert report._partition_protocols([]) == ([], [])


def test_report_bytes_preserve_sections_and_raw_only_condition():
    assert hashlib.sha256(_render().encode()).hexdigest() == EXPECTED_REPORT_HASH
    raw_only = report.render_markdown([_summaries()[1]], [], SimpleNamespace())
    assert hashlib.sha256(raw_only.encode()).hexdigest() == EXPECTED_RAW_ONLY_HASH


# Captured from the unmodified A2 input using the synthetic cases above.
EXPECTED_REPORT_HASH = 'd1c323deb9693dca0f482c1855f07b8058df20f953826d0b6d6760ccc34fbdac'
EXPECTED_RAW_ONLY_HASH = '1281ae0bb40d9fe602e2938efeab3d4dec2494ce2302a8389e07e39aaec1eaf3'
