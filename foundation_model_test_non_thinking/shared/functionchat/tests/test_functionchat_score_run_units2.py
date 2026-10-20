"""R4 contracts captured by executing original blocks on synthetic inputs."""
import shared.functionchat.scoring.score_run as subject


def test_unmeasured_coverage_counts():
    actual = subject._not_measured_coverage({'not_measured': {'call_decision': {'judge': 2, 'zero': 0}, 'dialog': {'text': 1}}}, {'call_decision': {'not_measured': {'judge': 2}}, 'dialog': {'not_measured': {'text': 1}}})
    assert actual == ({'judge': 2, 'zero': 0}, {'text': 1}, 3)


def test_unmeasured_coverage_mismatch():
    try:
        subject._not_measured_coverage({}, {'call_decision': {'not_measured': {'judge': 1}}})
    except ValueError as exc:
        actual = (type(exc).__name__, str(exc))
    assert actual == ('ValueError', "CallDecision not-measured counts disagree: coverage={}, raw={'judge': 1}")
