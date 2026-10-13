"""R4 contracts captured by executing original blocks on synthetic inputs."""
import shared.agent.scoring.validate_rules as subject


def test_v3_levels_empty():
    actual = ['existing']
    subject._check_v3_levels({}, failures=actual)
    assert actual == ['existing']


def test_v3_levels_failures_order():
    actual = ['existing']
    subject._check_v3_levels({'bad': {}, 'L1': {'score': 2, 'metrics': {}}, 'L2': {'score': None}}, failures=actual)
    assert actual == ['existing',
     "scoring_v3 invalid level entry: 'bad'",
     'scoring_v3.L1.score must be finite and within [0, 1], got 2',
     "scoring_v3.L1 in_score metric set mismatch: expected ['ArgF1_det', 'CallEM', 'ToolAcc'], got []",
     'scoring_v3.L1.ToolAcc metric is missing',
     'scoring_v3.L1.CallEM metric is missing',
     'scoring_v3.L1.ArgF1_det metric is missing',
     'scoring_v3.L2.metrics must be an object']


def test_v3_headline_incomplete():
    actual = []
    subject._check_v3_headline({}, {}, failures=actual)
    assert actual == ["scoring_v3.agent_score_status must be 'complete' or 'incomplete'"]


def test_v3_headline_mean():
    actual = []
    levels = {level: {'score': 0.5} for level in subject.SCORABLE_LEVELS}
    subject._check_v3_headline({'agent_score': 0.25, 'agent_score_status': 'complete', 'scored_levels': len(levels), 'required_levels': len(levels)}, levels, failures=actual)
    assert actual == ['scoring_v3.agent_score mean invariant failed: got 0.25, expected 0.5']


def test_v4_headline_incomplete():
    actual = []
    subject._check_v4_headline({}, {}, failures=actual)
    assert actual == ["scoring_v4.agent_score_status must be 'complete' or 'incomplete'",
     'scoring_v4.scored_levels must equal 0',
     'scoring_v4.required_levels must equal 5']


def test_v4_headline_mean():
    actual = []
    levels = {level: {'score': 0.5} for level in subject.V4_HEADLINE_LEVELS}
    subject._check_v4_headline({'agent_score': 0.25, 'agent_score_status': 'complete', 'scored_levels': len(levels), 'required_levels': len(levels)}, levels, failures=actual)
    assert actual == ['scoring_v4.agent_score mean invariant failed: got 0.25, expected 0.5']
