"""입력: 검증된 코호트의 기존·재채점 평균과 출처. 출력: 참고 지표 Markdown(순수)."""

from shared.multimodal.publish.report import _escape

NOTICE = "참고 지표 — 발행 게이트 판정과 별개, 공식 리더보드 점수와 동등하지 않음(저장 판정 기반)"


def render_section(cohorts, rejected=()):
    """같은 반복 집합의 두 평균을 표로 만들고 대표·반복·지표 근거를 붙인다."""
    out = ["## 참고 지표 — 공식 방식 재채점", "", NOTICE, "",
           "기존·재채점 값은 같은 반복 집합의 평균입니다. 차이는 재채점−기존(pp)이며 지표 간 정의가 다릅니다.",
           "", "| 모델 | 지표 | protocol | 반복 | 기존 평균 (%) | 재채점 평균 (%) | 차이 (pp) |",
           "|---|---|---|---:|---:|---:|---:|"]
    for value in cohorts:
        old, new = value["old_mean"], value["new_mean"]
        out.append(f'| {_escape(value["model"])} | `{value["metric"]}` | '
                   f'`{value["cohort"][2]}` | {value["repetitions"]} | '
                   f'{100 * old:.4f} | {100 * new:.4f} | {100 * (new - old):+.4f} |')
    if not cohorts:
        out.extend(["", "표시 가능한 재채점 코호트가 없습니다."])
    for value in rejected:
        out.append(f'\n- 재채점 제외: {_escape(value["model"])} · '
                   f'`{value["cohort"][2]}` — {_escape(value["reason"])}')
    out.extend(["", "<details>", "<summary>대표·반복 및 재채점 근거</summary>", ""])
    for value in cohorts:
        out.append(f'- {_escape(value["model"])} · `{value["metric"]}` · 대표: `{value["representative"]}`')
        for run in value["runs"]:
            out.append(f'  - 반복: `{run["source"]}` · revision `{run["revision"]}`')
    upstreams = {v["metric"]: v["upstream"] for v in cohorts if v["upstream"]}
    for metric, source in sorted(upstreams.items()):
        out.append(f'- `{metric}` v1: {source["repository"]}/blob/{source["commit"]}/{source["path"]}')
    out.extend(["", "</details>", ""])
    return "\n".join(out)
