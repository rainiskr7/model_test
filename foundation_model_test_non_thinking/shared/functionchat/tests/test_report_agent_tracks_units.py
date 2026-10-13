"""Representative selection and report bytes from synthetic original-code runs."""
import hashlib
from reports import report_agent_tracks as report


def _rows():
    return [
        {'publishable': True, 'track': 'functionchat', 'model': 'm', 'run': name,
         'axes': [('exact', 1, denominator, False), ('judged', 1, 2, True)],
         'judge_provenance_missing': ['endpoint']}
        for name, denominator in [('z', 2), ('a', 2), ('wide', 3)]
    ] + [{'publishable': False, 'track': 'functionchat', 'model': 'bad', 'run': 's', 'failures': []}]


def _render(rows):
    return report.render_markdown(rows, [{
        'status': 'DIVERGED', 'model': 'm', 'scoring_version': 'v1',
        'runs': ['z', 'a'], 'passed_counts': [1, 1], 'count_spread': 0,
        'stable_passed': 0, 'unstable_items': ['x'], 'reason': 'synthetic',
        'sampling_controls_removed': True, 'removed_sampling_params': ['seed'],
    }])


def test_axis_selection_keeps_ties_and_replaces_with_wider_run():
    best, ambiguous = report._select_axis_runs(_rows()[:-1])
    assert [(key, item[1]['run']) for key, item in best.items()] == [
        (('functionchat', 'm', 'exact'), 'wide'), (('functionchat', 'm', 'judged'), 'z')]
    assert ambiguous == {('functionchat', 'm', 'judged'): ['z', 'a', 'wide']}


def test_empty_axis_selection():
    assert report._select_axis_runs([]) == ({}, {})


def test_report_bytes_include_ties_rejection_and_reproducibility():
    assert hashlib.sha256(_render(_rows()).encode()).hexdigest() == EXPECTED_REPORT_HASH
    assert hashlib.sha256(report.render_markdown([]).encode()).hexdigest() == EXPECTED_EMPTY_HASH


# Captured from the unmodified A2 input using the synthetic cases above.
EXPECTED_REPORT_HASH = '005306f5bdf34f174e4c2dc5bf5c411c65ed1ae86a2d96dc03e016c1462f83a2'
EXPECTED_EMPTY_HASH = '722a1528cc9838874c67e9e4e236c1b90d555dd6c2c354efaa82998bd73457c6'
