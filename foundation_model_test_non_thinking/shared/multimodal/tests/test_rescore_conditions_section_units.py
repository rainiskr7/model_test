"""입력: 합성 선택 코호트·서빙 선언. 출력: judge 기록·미기록·세션 한정 표시 검증."""

from copy import deepcopy

from shared.multimodal.rescore.conditions_section import render_conditions


def selected():
    return [{"benchmark_id": "KOFFVQA-judge", "model": "served",
             "model_identity": {"canonical_id": "canonical"},
             "protocol": {"fingerprint": "fp"},
             "_selection": {"cohort_runs": [
                 {"session": "r1", "protocol": {"recorded": {"judge_model": "judge-one"}}},
                 {"session": "r2", "protocol": {"recorded": {"judge_model": "judge-one"}}}]}}]


def test_empty_scope_and_required_fixed_caveats():
    text = render_conditions([], [])
    assert "선택된 실행이 없습니다." in text
    assert "google/gemma-2-9b-it" in text and "lmms" in text
    assert "tau" not in text and "solo" not in text


def test_declared_condition_only_matches_canonical_model_and_explicit_session():
    cohorts = selected()
    declarations = [{"model": "canonical", "sessions": ["r2"], "generation_config": "vllm",
                     "evidence": "deployment|record"},
                    {"model": "other", "sessions": ["r1"], "generation_config": "auto", "evidence": "ignore"}]
    before = deepcopy((cohorts, declarations))
    text = render_conditions(cohorts, declarations)
    assert "| canonical | `fp` | judge-one | 2 |" in text
    assert "| canonical | r1 | 미기록 | 선언 없음 |" in text
    assert "| canonical | r2 | vllm | deployment\\|record |" in text
    assert "ignore" not in text and "실측 기록이 아닙니다" in text
    assert (cohorts, declarations) == before


def test_missing_judge_and_all_undeclared_sessions_remain_unknown():
    cohorts = selected()
    for run in cohorts[0]["_selection"]["cohort_runs"]:
        run["protocol"]["recorded"].clear()
    text = render_conditions(cohorts, [])
    assert "| canonical | `fp` | 미기록 | 2 |" in text
    assert "| canonical | r1, r2 | 미기록 | 선언 없음 |" in text
