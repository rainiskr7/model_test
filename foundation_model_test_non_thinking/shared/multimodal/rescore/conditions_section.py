"""입력: 선택된 multimodal 코호트·세션별 서빙 선언. 출력: 평가 조건 Markdown(순수)."""

from shared.multimodal.publish.report import _escape
from shared.multimodal.publish.schema import canonical_model_id


def render_conditions(selected, declarations):
    """judge는 선택 코호트의 기록, generation-config는 적용 세션의 선언으로만 표시한다."""
    out = ["## 평가 조건 — 공식과 다른 점", "",
           "- K-MMBench 기존 지표는 행 정답률, 참고 지표는 manifest 순환 묶음 통과율입니다.",
           "- MTVQA 기존 판정과 lmms 판정은 다릅니다. 참고 판정은 singleton gold·빈 gold·오류 처리의 로컬 예외를 포함합니다.",
           "- KOFFVQA 공식 기본 judge는 `google/gemma-2-9b-it`입니다. 아래는 선택 코호트의 저장 judge입니다.",
           "", "| 모델 | protocol | 저장 judge | 반복 |", "|---|---|---|---:|"]
    judges = [v for v in selected if v["benchmark_id"] == "KOFFVQA-judge"]
    for value in judges:
        runs = value["_selection"]["cohort_runs"]
        names = sorted({str(r["protocol"]["recorded"].get("judge_model") or "미기록") for r in runs})
        out.append(f'| {_escape(canonical_model_id(value))} | `{value["protocol"]["fingerprint"]}` | '
                   f'{_escape(", ".join(names))} | {len(runs)} |')
    if not judges:
        out.extend(["", "선택 범위에 발행 가능한 judge 코호트가 없습니다."])
    out.extend(["", "### vLLM generation-config 선언", "",
                "서빙 선언은 실측 기록이 아닙니다. 명시된 모델·세션에만 적용하며 미기록을 auto로 추정하지 않습니다.",
                "", "| 모델 | 적용 세션 | generation-config | 근거 |", "|---|---|---|---|"])
    by_session = {(d["model"], s): (d["generation_config"], d["evidence"])
                  for d in declarations for s in d["sessions"]}
    observed = {(canonical_model_id(v), str(r.get("session"))) for v in selected
                for r in v["_selection"]["cohort_runs"]}
    grouped = {}
    for model, session in sorted(observed):
        config, evidence = by_session.get((model, session), ("미기록", "선언 없음"))
        grouped.setdefault((model, config, evidence), []).append(session)
    for (model, config, evidence), sessions in grouped.items():
        out.append(f'| {_escape(model)} | {_escape(", ".join(sessions))} | '
                   f'{_escape(config)} | {_escape(evidence)} |')
    if not observed:
        out.extend(["", "선택된 실행이 없습니다."])
    out.append("")
    return "\n".join(out)
