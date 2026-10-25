"""R4 contracts captured by executing original blocks on synthetic inputs."""
import pytest
import shared.taubench.scoring.cohort as subject


@pytest.mark.parametrize("value", [None, ""])
def test_comparison_facts_empty(value):
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
    empty = {"harness_integrity": {"user_provider": value, "user_reasoning_effort": value}}
    assert list(subject._comparison_facts(empty).items()) == actual
    assert subject.comparison_fingerprint(empty) == subject.comparison_fingerprint({})


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
    baseline = {"harness_integrity": {"mode": "standard", "user_request_timeout": 120.0,
                                    "user_max_tokens": 16384, "user_model_sent_to_litellm": "openrouter/openai/gpt-oss-120b"}}
    fingerprints = {subject.comparison_fingerprint(baseline)["fingerprint"]}
    for provider, effort in (("deepinfra/bf16", "medium"), ("other/provider", "medium"),
                             ("deepinfra/bf16", "low"), ("deepinfra/bf16", None), (None, "medium")):
        summary = {"harness_integrity": {**baseline["harness_integrity"],
                    "user_provider": provider, "user_reasoning_effort": effort}}
        result = subject.comparison_fingerprint(summary)
        for key, value in (("user_provider", provider), ("user_reasoning_effort", effort)):
            if value:
                assert result["facts"][key] == value
            else:
                assert key not in result["facts"]
        assert result["fingerprint"] not in fingerprints
        fingerprints.add(result["fingerprint"])
        assert subject.comparison_fingerprint({**summary, "model": "different-candidate"}) == result
