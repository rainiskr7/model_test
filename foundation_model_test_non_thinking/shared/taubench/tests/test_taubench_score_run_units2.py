"""R4 contracts captured by executing original blocks on synthetic inputs."""
import json
import pytest
from shared.taubench.scoring import cohort
import shared.taubench.scoring.score_run as subject


@pytest.mark.parametrize("case", [
    "valid", "provider_only", "effort_only", "provider", "effort", "extra_missing", "extra_null",
    "extra_string", "extra_list", "provider_missing", "provider_null", "provider_string", "provider_list",
    "order_missing", "order_empty", "order_two", "order_string", "order_nonstring", "order_null",
    "fallbacks_missing", "fallbacks_true", "fallbacks_zero", "require_missing", "require_false", "require_one",
    "reasoning_missing", "reasoning_null", "reasoning_list", "reasoning_string", "effort_missing", "effort_null", "effort_number",
])
def test_observed_protocol_mismatch(case, tmp_path):
    """설정 대조 오류는 저장된 summary와 비교·발행 게이트까지 전달한다.

    유지: 사용자 지시(새 함수 금지), Stage 4
    """
    failures, warnings = ['existing'], []
    subject._validate_observed_user_protocol({'harness_integrity': {'upstream_result_evidence': {'user_protocol': {'mismatch': ['model']}}}}, failures=failures, warnings=warnings)
    actual = (failures, warnings)
    assert actual == (['existing', "사용자 시뮬레이터 프로토콜이 선언과 다르다 — 다른 런과 비교할 수 없다: ['model']"], [])
    integrity = {
        "mode": "standard", "agent_implementation": "llm_agent", "user_implementation": "user_simulator",
        "model_sent_to_litellm": "openai/candidate", "request_timeout": 60.0, "max_tokens": 16384,
        "user_model_sent_to_litellm": "openrouter/openai/gpt-oss-120b",
        "user_request_timeout": 120.0, "user_max_tokens": 16384, "user_temperature": 0.0,
        "user_provider": "deepinfra/bf16", "user_reasoning_effort": "medium",
    }
    extra = {"provider": {"order": ["deepinfra/bf16"], "allow_fallbacks": False, "require_parameters": True},
             "reasoning": {"effort": "medium"}}
    if case in ("provider_only", "effort_only"):
        key, field = ("user_reasoning_effort", "reasoning") if case == "provider_only" else ("user_provider", "provider")
        del integrity[key], extra[field]
    elif case == "provider":
        extra["provider"]["order"] = ["other/provider"]
    elif case == "effort":
        extra["reasoning"]["effort"] = "low"
    elif case.startswith("order_"):
        extra["provider"].pop("order")
        if case != "order_missing":
            extra["provider"]["order"] = {"order_empty": [], "order_two": ["deepinfra/bf16", "other"],
                "order_string": "deepinfra/bf16", "order_nonstring": [1], "order_null": None}[case]
    elif case.startswith("fallbacks_") or case.startswith("require_"):
        field = "allow_fallbacks" if case.startswith("fallbacks_") else "require_parameters"
        extra["provider"].pop(field)
        if not case.endswith("missing"):
            extra["provider"][field] = {"fallbacks_true": True, "fallbacks_zero": 0,
                                       "require_false": False, "require_one": 1}[case]
    elif case.startswith("effort_"):
        extra["reasoning"].pop("effort")
        if case != "effort_missing":
            extra["reasoning"]["effort"] = None if case == "effort_null" else 1
    elif case.startswith("provider_") or case.startswith("reasoning_"):
        field, kind = case.split("_")
        extra.pop(field)
        if kind != "missing":
            extra[field] = {"null": None, "string": "bad", "list": []}[kind]
    user_args = {"timeout": 120.0, "max_tokens": 16384, "temperature": 0.0}
    if case != "extra_missing":
        user_args["extra_body"] = {"extra_null": None, "extra_string": "bad", "extra_list": []}.get(case, extra)
    raw = {"info": {
        "agent_info": {"implementation": "llm_agent", "llm": "openai/candidate",
                       "llm_args": {"timeout": 60.0, "max_tokens": 16384, "num_retries": 0}},
        "user_info": {"implementation": "user_simulator", "llm": "openrouter/openai/gpt-oss-120b", "llm_args": user_args}},
        "tasks": [{"id": "one", "evaluation_criteria": {"reward_basis": ["ENV_ASSERTION"]}}],
        "simulations": [{"task_id": "one", "termination_reason": "agent_stop", "reward_info": {"reward": 1}, "messages": []}]}
    manifest = {"status": "completed", "model": "candidate", "harness_integrity": integrity,
                "split": {"domain": "telecom", "name": "test", "task_ids": ["one"],
                          "task_count": 1, "runnable_task_count": 1,
                          "not_measured_task_count": 0, "not_measured_tasks": []}}
    (tmp_path / "run_manifest.json").write_text(json.dumps(manifest))
    upstream = tmp_path / "upstream/telecom"
    upstream.mkdir(parents=True)
    (upstream / "results.json").write_text(json.dumps(raw))
    valid = case in ("valid", "provider_only", "effort_only")
    assert subject.main(["--results-dir", str(tmp_path)]) == (0 if valid else 1)
    summary = json.loads((tmp_path / "summary.json").read_text())
    protocol = summary["harness_integrity"]["upstream_result_evidence"]["user_protocol"]
    assert protocol["pinned"] is True
    assert "configuration, not wire evidence" in protocol["source"]
    assert ("mismatch" not in protocol) is valid
    assert summary["publish_status"]["publishable"] is valid
    assert cohort.comparison_fingerprint(summary)["comparable_across_candidates"] is valid
    if not valid:
        assert any("비교할 수 없다" in message for message in summary["publish_status"]["failures"])
        if case not in ("provider", "effort"):
            assert any(str(value).startswith("invalid:") for key, value in protocol.items()
                       if key in ("user_provider", "user_reasoning_effort"))


def test_observed_protocol_unpinned():
    failures, warnings = [], []
    subject._validate_observed_user_protocol({'harness_integrity': {'upstream_result_evidence': {'user_protocol': {'pinned': False}}}}, failures=failures, warnings=warnings)
    actual = (failures, warnings)
    assert actual == ([], ['사용자 시뮬레이터 인자가 기록돼 있지 않다 — 이 런은 모델 간 비교에 쓸 수 없다'])


def test_domain_coverage_out_of_scope():
    failures, warnings = [], []
    subject._validate_domain_coverage({'by_domain': {'retail': {'runnable_tasks': 0, 'status': 'not_measured'}}}, failures=failures, warnings=warnings)
    actual = (failures, warnings)
    assert actual == ([], [])


def test_domain_coverage_partial_infrastructure():
    failures, warnings = [], []
    subject._validate_domain_coverage({'harness_integrity': {'trials': 2}, 'by_domain': {'retail': {'runnable_tasks': 3, 'measured': 2, 'trials': [1, 2], 'benchmark_eligible': False, 'coverage': {'official_task_count': 4}, 'termination_reasons': {'infrastructure_error': 2}, 'candidate_protocol_failures': {'empty': 1}, 'incompletion_attribution': {'environment': {'timeout': 1}}}}}, failures=failures, warnings=warnings)
    actual = (failures, warnings)
    assert actual == (['by_domain.retail: 3개 과제 중 2개만 측정됐다 — 부분 실행이다',
      'by_domain.retail: 시행 수가 과제마다 다르다 (선언 2, 관측 [1, 2]) — Pass^k 를 낼 수 없다',
      'by_domain.retail: 완주 실패 1건 (environment=1) — 완전 측정이 아니다'],
     ['by_domain.retail: 공식 split 4건 중 3건만 대상이다 — 도메인 점수가 아니라 부분집합 점수로만 인용할 것'])
