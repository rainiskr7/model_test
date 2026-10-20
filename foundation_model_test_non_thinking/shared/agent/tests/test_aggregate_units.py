"""Synthetic aggregation contracts captured from the original implementation."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from shared.agent.scoring import aggregate
from shared.agent.scoring.aggregate_coverage import _format_l7_coverage


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


def test_collect_and_format_empty_l7():
    distribution, per_field, entries, coverage = aggregate._collect_l7_coverage({})
    assert distribution == per_field == {}
    assert entries == 0
    assert coverage == EXPECTED_EMPTY_COVERAGE
    assert _digest(_format_l7_coverage(distribution, per_field, entries, coverage)) == EXPECTED_EMPTY_L7_HASH


def test_collect_and_format_partial_l7():
    task = {'golden_fields': [{'fields': ['price', 'title']}]}
    with patch.object(aggregate, 'build_eval_context', return_value=object()), \
         patch.object(aggregate, 'result_field_coverage_diagnostics', return_value={}), \
         patch.object(aggregate, 'result_field_coverage_entry_diagnostics', return_value=[{
             'fields_required': 2, 'fields_present': 1,
             'fields': [{'field': 'title', 'present': True}, {'field': 'price', 'present': False}],
         }]):
        collected = aggregate._collect_l7_coverage({'results': [task, None]})
    assert collected[0] == {(2, 1): 1}
    assert list(collected[1]) == ['title', 'price']
    assert _digest(_format_l7_coverage(*collected)) == EXPECTED_PARTIAL_L7_HASH


def test_build_v2_summary_empty():
    summary = aggregate._build_v2_summary({}, Path('/synthetic/model/session/language/agent'))
    assert _digest(summary) == EXPECTED_V2_HASH


def test_v3_append_preserves_existing_keys():
    summary = {'sentinel': True}
    levels = {level: {'score': 0.5} for level in aggregate.SCORABLE_LEVELS}
    aggregate._add_v3_summary(levels, 6, [], {}, summary)
    assert list(summary) == ['sentinel', 'scoring_v3']
    assert summary['scoring_v3']['agent_score'] == 0.5
    assert summary['scoring_v3']['agent_score_status'] == 'complete'


# Captured from the unmodified A2 input using the synthetic cases above.
EXPECTED_EMPTY_COVERAGE = {'tasks_total': 0,
 'tasks_classifiable': 0,
 'tasks_unclassifiable': 0,
 'golden_entries_declared': 0,
 'golden_entries_classifiable': 0,
 'golden_entries_unclassifiable': 0,
 'fields_declared': 0,
 'fields_excluded_long_text': 0,
 'fields_unresolved': 0,
 'context_construction_failures': {'count': 0}}
EXPECTED_EMPTY_L7_HASH = '8bd9c9832a3696e468a4740e44f479db343a6aab5d3214d7d07f316b9467957d'
EXPECTED_PARTIAL_L7_HASH = '182bfb4e213fee563cfa7613ff524905bb8925c79fa7997651b10c3ac71dcfba'
EXPECTED_V2_HASH = '59b68e8bfa5e5c76ab1310a19c244bd71132e7926dd3864f2d3f6d747b4526cf'
