"""Small synthetic cases; expected values were captured from the A2 original."""
import hashlib
import json
import pytest
from shared.taubench.scoring import score_run as scorer


def _fixture():
    raw = {
        'tasks': [{'id': 'a', 'evaluation_criteria': {'reward_basis': ['DB']}}],
        'simulations': [
            {'task_id': 'a', 'termination_reason': 'agent_stop', 'reward_info': {'reward': 1}},
            {'task_id': 'a', 'termination_reason': 'agent_stop', 'reward_info': {'reward': 0}},
            {'task_id': 'unknown', 'termination_reason': 'agent_stop'},
        ],
        'info': {'agent_info': {'implementation': 'llm_agent_solo', 'llm_args': {'num_retries': 0}},
                 'user_info': {'implementation': 'dummy_user'}},
    }
    manifest = {'status': 'completed', 'model': 'test/model', 'split': {
        'name': 'test', 'task_ids': ['a'], 'runnable_task_count': 1,
        'not_measured_tasks': [], 'not_measured_task_count': 0, 'task_count': 1,
    }}
    return raw, manifest


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


def test_score_simulations_counts_and_record_order():
    raw, _ = _fixture()
    records, passed, failed, measured, missing, protocol, simulations = scorer._score_simulations(raw)
    assert (passed, failed, measured, dict(missing), dict(protocol)) == (1, 1, 2, {'reward_basis_missing': 1}, {})
    assert records == EXPECTED_RECORDS
    assert simulations == raw['simulations']


@pytest.mark.parametrize('measured,passed,candidate,environment,expected', [
    (2, 1, {'failure@agent': 1}, {}, (1 / 3, 3, None)),
    (0, 0, {}, {}, (None, 0, '완주한 시뮬레이션이 없다')),
])
def test_strict_pass_rate(measured, passed, candidate, environment, expected):
    assert scorer._strict_pass_rate(measured, passed, candidate, environment, {}) == expected


def test_validated_split_and_domain_order():
    raw, manifest = _fixture()
    split, count, excluded, excluded_count, domain, upstream = scorer._validated_split({'telecom': raw}, manifest)
    assert (split, count, excluded, excluded_count, domain, upstream) == (manifest['split'], 1, [], 0, 'telecom', raw)
    domains = scorer._score_selected_domains(manifest, domain, upstream, count)
    assert list(domains) == ['telecom', 'banking_knowledge', 'retail', 'airline']
    assert _digest(domains) == EXPECTED_DOMAINS_HASH


def test_validated_split_keeps_first_error():
    with pytest.raises(ValueError, match='^run manifest is not completed$'):
        scorer._validated_split({}, {'split': {'runnable_task_count': 9}})


def test_summary_payload_and_public_summary_preserve_bytes():
    raw, manifest = _fixture()
    domains = scorer._score_selected_domains(manifest, 'telecom', raw, 1)
    scorer._annotate_domain_coverage(manifest['split'], 1, domains['telecom'])
    payload = scorer._summary_payload(manifest, 'tau', manifest['split'], domains, raw, 0, [])
    assert _digest(payload) == EXPECTED_SUMMARY_HASH
    assert _digest(scorer.build_summary({'telecom': raw}, manifest, 'tau')) == EXPECTED_SUMMARY_HASH


# Captured from the unmodified A2 input using the synthetic cases above.
EXPECTED_RECORDS = [{'task_id': 'a',
  'reward_basis': ['DB'],
  'evaluation_status': 'measured',
  'upstream_reward': 1,
  'termination_reason': 'agent_stop',
  'passed': True},
 {'task_id': 'a',
  'reward_basis': ['DB'],
  'evaluation_status': 'measured',
  'upstream_reward': 0,
  'termination_reason': 'agent_stop',
  'passed': False},
 {'task_id': 'unknown',
  'reward_basis': [],
  'evaluation_status': 'not_measured',
  'upstream_reward': None,
  'termination_reason': 'agent_stop',
  'not_measured_reason': 'reward_basis_missing'}]
EXPECTED_DOMAINS_HASH = '93d7a06685a013fe6f19b17277cf6d2713f00c1263e58240c10eaa9d42c0289f'
EXPECTED_SUMMARY_HASH = '7cb399c64963513cd2be063de9f9c9f99e444dc9db51e4ed57b3f6e3390c1583'


@pytest.mark.parametrize('case', [
    'original', 'serving', 'timeout', 'server', 'mixed', 'other_message',
    'user', 'unknown', 'both_actors', 'empty', 'non_infra', 'measured',
])
def test_domain_summary_combines_scored_records_and_attribution(case, tmp_path, capsys):
    raw, _ = _fixture()
    result = scorer._domain_summary(1, scorer._score_simulations(raw))
    assert _digest(result) == EXPECTED_DOMAIN_HASH
    if case == 'original':
        return
    raw, manifest = _fixture()
    raw['tasks'] = [{'id': str(i), 'evaluation_criteria': {'reward_basis': ['DB']}} for i in range(40)]
    raw['simulations'] = [{
        'task_id': str(i), 'termination_reason': 'infrastructure_error',
        'info': {'error_type': 'BadRequestError',
                 'error': ' litellm.BadRequestError: OpenAIException - No user query found in messages.\n',
                 'error_traceback': 'self.agent.generate_next_message'},
    } for i in range(40)]
    for sim in raw['simulations']:
        if case in ('timeout', 'server'):
            sim['info']['error_type'] = 'Timeout' if case == 'timeout' else 'InternalServerError'
        elif case == 'other_message':
            sim['info']['error'] = 'different BadRequest'
        elif case in ('user', 'unknown', 'both_actors'):
            sim['info']['error_traceback'] = {
                'user': 'self.user.generate_next_message', 'unknown': '',
                'both_actors': 'self.agent.generate_next_message self.user.generate_next_message',
            }[case]
    if case == 'mixed':
        raw['simulations'][-1]['info']['error_type'] = 'APIError'
    elif case == 'empty':
        raw['simulations'] = []
    elif case in ('non_infra', 'measured'):
        raw['simulations'][-1]['termination_reason'] = 'agent_stop'
        if case == 'measured':
            raw['simulations'][-1]['reward_info'] = {'reward': 1}
    manifest['split'].update(task_ids=[str(i) for i in range(40)], task_count=40, runnable_task_count=40)
    upstream = tmp_path / 'upstream/telecom'
    upstream.mkdir(parents=True)
    (upstream / 'results.json').write_text(json.dumps(raw))
    (tmp_path / 'run_manifest.json').write_text(json.dumps(manifest))
    assert scorer.main(['--results-dir', str(tmp_path)]) == 1
    summary = json.loads((tmp_path / 'summary.json').read_text())
    entry = summary['by_domain']['telecom']
    expected = ('serving_incompatible:template_requires_user_turn' if case == 'serving'
                else None if case == 'measured' else 'no upstream records had a runnable numeric reward')
    assert entry['reason'] == expected
    assert summary['publish_status']['publishable'] is False
    assert (entry['measured'], entry['passed'], entry['failed'], entry['pass_rate']) == (
        (1, 1, 0, 1.0) if case == 'measured' else (0, 0, 0, None))
    assert entry['candidate_protocol_failures'] == {}
    if case == 'serving':
        assert entry['incompletion_attribution']['environment'] == {'BadRequestError@agent': 40}
        assert expected in capsys.readouterr().err

EXPECTED_DOMAIN_HASH = 'e1cea74c186ac30b0bffae23cb8d4db9d02183f271c4dbb4a8567467862cecd9'
