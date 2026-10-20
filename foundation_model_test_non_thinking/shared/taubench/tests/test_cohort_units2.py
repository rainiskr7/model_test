"""R4 contracts captured by executing original blocks on synthetic inputs."""
import shared.taubench.scoring.cohort as subject


def test_comparison_facts_empty():
    actual = list(subject._comparison_facts({}).items())
    assert actual == [('benchmark', None),
     ('scoring_version', None),
     ('domain', None),
     ('split_name', None),
     ('task_set_digest', '4f53cda18c2baa0c'),
     ('official_task_count', None),
     ('runnable_task_count', None),
     ('mode', None),
     ('agent_implementation', None),
     ('user_implementation', None),
     ('user_model', None),
     ('user_request_timeout', None),
     ('user_max_tokens', None),
     ('max_steps', None),
     ('tau2_version', None),
     ('trials', None)]


def test_comparison_facts_protocol():
    actual = list(subject._comparison_facts({'model': 'candidate', 'benchmark': 'tau', 'scoring_version': 'v', 'split': {'domain': 'retail', 'name': 'test', 'task_ids': ['b', 'a'], 'task_count': 2, 'runnable_task_count': 2}, 'harness_integrity': {'mode': 'solo', 'trials': 3, 'request_timeout': 99, 'user_max_tokens': 8}}).items())
    assert actual == [('benchmark', 'tau'),
     ('scoring_version', 'v'),
     ('domain', 'retail'),
     ('split_name', 'test'),
     ('task_set_digest', '0473ef2dc0d324ab'),
     ('official_task_count', 2),
     ('runnable_task_count', 2),
     ('mode', 'solo'),
     ('agent_implementation', None),
     ('user_implementation', None),
     ('user_model', None),
     ('user_request_timeout', None),
     ('user_max_tokens', 8),
     ('max_steps', None),
     ('tau2_version', None),
     ('trials', 3)]
