"""입력: 비교 쌍과 이미 채점된 코호트 또는 비교 결과. 출력: paired 결과·Markdown(순수)."""

from shared.multimodal.publish.report import _escape
from shared.stats.__main__ import comparison
from shared.stats.paired import INTERPRETATION
from shared.stats.selection import SelectionError


def compare_pairs(pairs, cohorts, seed=0, resamples=2000):
    """같은 CLI 계산을 적용하며 검증 거부만 결과로 남기고 구현 예외는 전파한다."""
    results = []
    for pair in pairs:
        try:
            values = [cohorts.get((pair[side], pair["bench"])) for side in ("a", "b")]
            for value in values:
                if isinstance(value, SelectionError):
                    raise value
                if value is None:
                    raise SelectionError("범위 내 발행 가능 코호트 없음")
            results.append({**pair, "result": comparison(*values, seed=seed, resamples=resamples)})
        except SelectionError as exc:
            results.append({**pair, "error": str(exc), "candidates": exc.candidates})
    return results


def render_pairs(results):
    """차이·구간은 pp로, 성공·검증 거부는 빠짐없이 표와 출처 목록으로 반환한다."""
    out = ["## 참고 지표 — 모델 간 paired 비교", "", INTERPRETATION + " (반복 간 변동 미포함).",
           "차이 = A−B. 이미지 클러스터를 함께 재표집하며 문항 가중 평균을 사용합니다.", "",
           "| A 폴더 | B 폴더 | 벤치 | 차이 (pp) | 95% 구간 (pp) | 문항 / 이미지 | 반복 A/B |",
           "|---|---|---|---:|---|---:|---:|"]
    for value in results:
        prefix = f'| {_escape(value["a"])} | {_escape(value["b"])} | {value["bench"]} |'
        if "error" in value:
            out.append(prefix + f' 비교 불가: {_escape(value["error"])} | — | — | — |')
        else:
            r = value["result"]
            out.append(prefix + f' {100 * r["difference"]:+.4f} | '
                       f'[{100 * r["ci95"][0]:+.4f}, {100 * r["ci95"][1]:+.4f}] | '
                       f'{r["items"]} / {r["images"]} | {r["repetitions_a"]}/{r["repetitions_b"]} |')
    if not results:
        out.extend(["", "선언된 비교 쌍이 없습니다."])
    out.extend(["", "<details>", "<summary>paired 계산·반복 근거</summary>", ""])
    for value in results:
        if "result" not in value:
            continue
        r = value["result"]
        out.append(f'- {value["a"]} − {value["b"]} · `{r["metric"]}` · '
                   f'`{r["cohort"][2]}` · seed={r["seed"]}, resamples={r["resamples"]}')
        for side in ("a", "b"):
            for run in r[side]["runs"]:
                out.append(f'  - {side.upper()}: `{run["source"]}`')
    out.extend(["", "</details>", ""])
    return "\n".join(out)
