"""무엇: family 의미 분리 · 입력: 별칭/비표준 ID/빈 표본 · 출력: 의미 승계 · 계약 §7-6."""

from dataclasses import FrozenInstanceError, replace
import pytest
from jeveval.score.set_metrics import METRICS, metric_spec
from jeveval.score.population import population, qstats
from jeveval.score.observations import observations, question_ids
from jeveval.score.risk_mix import distributions
from jeveval.score.risk import risk_cell
from tests.score.population_support import question, answer, record, population_args


def test_registry_is_immutable_and_unknown_has_empty_meaning():
    with pytest.raises(TypeError): METRICS['x'] = metric_spec('kosgd')
    with pytest.raises(FrozenInstanceError): METRICS['kosgd'].slot_specific = False
    assert metric_spec('unknown').f1_undefined_labels == ()


def test_tool_label_not_id_controls_f1_and_observations():
    qs = [question('action', 'call', 'fc:type_of_output'), question('unusual', 'true', 'fc:tool')]
    rec = record(qs, {'action': answer('call', {'call': 1.}), 'unusual': answer()}, set_name='alias')
    args = population_args([rec], set_name='alias')
    args['spec'] = metric_spec('fc_call_decision')
    value = population(**args)
    assert value.questions['unusual'].macro_f1 is None
    assert [o.question_id for o in observations([rec[2]], args['items'], spec=args['spec'])] == ['action']
    assert question_ids(args['items'], spec=args['spec']) == ['action']
    assert qstats('tool', 'success', 'noul', [(answer(), 'true')], 0).macro_f1 == 1.


@pytest.mark.parametrize('family', ['fc_call_decision', 'korfin_asc', 'kosgd'])
def test_alias_test_projection_equals_original_and_empty_shapes(family):
    qs = ([question('a', 'call', 'fc:type_of_output'), question('t', label='fc:tool')]
          if family == 'fc_call_decision' else [question('a', label='korfin:sentiment')]
          if family == 'korfin_asc' else [question('a')])
    records = [record(qs, {q.id: answer(q.gold, {q.gold: 1.}) for q in qs}, set_name=name) for name in (family, 'alias')]
    pops, obs = [], []
    spec = metric_spec(family)
    for name, rec in zip((family, 'alias'), records):
        args = population_args([rec], set_name=name); args['spec'] = spec
        pops.append(population(**args))
        obs.append([(o.question_id, o.answer, o.gold) for o in observations([rec[2]], args['items'], spec=spec)])
    assert pops[0] == pops[1] and obs[0] == obs[1]
    assert distributions([], {}, set(), spec=spec)[0]['by_service'] is None
    assert distributions([], {}, set(), spec=spec)[0]['by_stratum'] is None


def test_metric_spec_is_required_for_every_calculation():
    calls = [
        (population, (), dict(outcomes=[], finals=[], items={}, certified=False,
                              unit='group_representative', set_name='synthetic')),
        (observations, ([], {}), {}),
        (question_ids, ({},), {}),
        (distributions, ([], {}, set()), {}),
        (risk_cell, (), dict(tau='0.02', threshold=None, dev=[], test=[], test_items={})),
    ]
    for function, args, kwargs in calls:
        with pytest.raises(TypeError, match="required keyword-only argument: 'spec'"):
            function(*args, **kwargs)
