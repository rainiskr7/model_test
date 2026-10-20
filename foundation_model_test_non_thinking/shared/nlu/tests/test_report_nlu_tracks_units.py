"""Synthetic NLU report bytes captured before extraction."""
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from reports import report_nlu_tracks as report


def _scorer():
    return SimpleNamespace(
        compliance=lambda runs: {'scored_runs': 2, 'items': 4, 'honored': 3, 'invalid': 1,
                                 'per_model': {'m': {'items': 4, 'invalid': 1, 'runs': 2}}},
        discrimination=lambda runs: {
            'a': {'assessable': True, 'models': 2, 'distinct_answers': ['x', 'y'], 'discriminating': True, 'invalid_runs': 1},
            'b': {'assessable': False, 'models': 1, 'distinct_answers': [], 'invalid_runs': 0},
            'c': {'assessable': True, 'models': 2, 'distinct_answers': [], 'invalid_runs': 2},
        },
        stability=lambda runs: {('m', 'v1'): {'runs': 2, 'status': 'DIVERGED', 'unstable_items': {'a': ['x', 'y']},
                                             'sampling_controls_removed': True, 'removed_sampling_params': []}},
        constant_baseline=lambda: {'total_items': 2, 'best_constant_passes': 1, 'best_constant_labels': ['x']},
    )


def _render():
    runs = [{'scorable': True, 'model': 'm', 'session': 's', 'counts': {'pass': 1},
             'items': [{'item_id': 'a', 'status': 'pass'}, {'item_id': 'b', 'status': 'invalid'}]},
            {'scorable': False, 'session': 'bad', 'blockers': ['missing', 'broken']}]
    creds = {'m': {'claim_class': 'repeatability_observed', 'k': 3, 'instability_envelope': [0, 1],
                   'majority_passed': 1, 'measured_items': 2, 'count_range': [1, 1], 'unstable_items': []}}
    with patch.object(report, 'credentials', return_value=creds), \
         patch.object(report, '_claims', return_value=(None, lambda *args: None)):
        return report.render_markdown(runs, _scorer(), Path('/synthetic'))


def test_report_sections_preserve_original_bytes():
    assert hashlib.sha256(_render().encode()).hexdigest() == EXPECTED_REPORT_HASH


def test_empty_report_preserves_original_bytes():
    text = report.render_markdown([], _scorer())
    assert hashlib.sha256(text.encode()).hexdigest() == EXPECTED_EMPTY_HASH


# Captured from the unmodified A2 input using the synthetic cases above.
EXPECTED_REPORT_HASH = 'f6f0742cea17f943a69bb1f0ac308209a5e50c6bfe77ba5ff7b3bfd72d2abef9'
EXPECTED_EMPTY_HASH = 'e30cb998a696bc636d7a71dcbd949f4dfb9022ae69d8e48c71740d31ea7ed17b'


def test_collect_uses_running_package_when_results_base_is_absent(tmp_path):
    from shared.nlu.scoring import score_run

    runs, scorer = report.collect(tmp_path / "absent")
    assert runs == []
    assert scorer is score_run


def test_results_base_cannot_select_scorer_or_claims_code(tmp_path):
    from shared.nlu.scoring import score_run
    from shared.publish.claims import comparable, credential

    for relative in ("shared/nlu/scoring/score_run.py", "shared/publish/claims.py"):
        foreign = tmp_path / relative
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text('raise AssertionError("results base selected code")\n')
    assert report.collect(tmp_path) == ([], score_run)
    assert report._claims(tmp_path) == (credential, comparable)
