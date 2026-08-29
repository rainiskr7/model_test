#!/usr/bin/env python3
"""nlu 항목별 판정 벡터를 낸다. **점수도 순위도 내지 않는다.**

프롬프트 2개(항목 5개)는 스칼라 점수를 지탱하지 못한다. 이 도구가 내는 것은
모델 × 항목 행렬과, 그 행렬을 오독하지 않는 데 필요한 사실들이다 —
변별하지 못한 항목, 상수 전략 기준선, 채점하지 못한 런과 그 사유.

--strict 는 읽을 수 없거나 완결되지 않은 산출물이 있으면 1 로 끝난다(CI 용).
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

BASE_DEFAULT = Path(__file__).resolve().parent / "foundation_model_test_non_thinking"
STATUS_MARK = {"pass": "O", "fail": "X", "invalid": "-"}


def _load_scorer(base: Path):
    scoring_dir = base / "shared" / "nlu" / "scoring"
    spec = importlib.util.spec_from_file_location("nlu_score_run", scoring_dir / "score_run.py")
    if spec is None or spec.loader is None:
        raise SystemExit(f"채점기를 찾을 수 없다: {scoring_dir}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(scoring_dir))
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(scoring_dir))
        except ValueError:
            pass
    return module


def collect(base: Path) -> tuple[list[dict[str, Any]], Any]:
    scorer = _load_scorer(base)
    runs = [scorer.score_run(d) for d in sorted(base.glob("results/*/*/language/nlu"))]
    return runs, scorer


def render_markdown(runs: list[dict[str, Any]], scorer) -> str:
    scorable = [r for r in runs if r["scorable"]]
    out: list[str] = ["# NLU 항목별 판정", ""]
    out.append(
        "**이 표에는 점수가 없다.** 항목 5개짜리 벡터를 하나의 수로 접으면 그 수는 "
        "표본 크기를 숨긴다. 통과 개수는 세지만 평균도 순위도 만들지 않는다."
    )
    out.append("")

    if not scorable:
        out.append("채점 가능한 런이 없다.")
    else:
        item_ids = [entry["item_id"] for entry in scorable[0]["items"]]
        out.append("| 모델 | 세션 | " + " | ".join(item_ids) + " | 통과 |")
        out.append("|---|---|" + "---|" * (len(item_ids) + 1))
        for run in scorable:
            marks = {e["item_id"]: STATUS_MARK.get(e["status"], "?") for e in run["items"]}
            cells = " | ".join(marks.get(i, "?") for i in item_ids)
            out.append(
                f"| `{run['model']}` | `{run['session']}` | {cells} | "
                f"{run['counts']['pass']}/{len(item_ids)} |"
            )
        out.append("")
        out.append("O = 정답 라벨 · X = 다른 라벨 · − = 계약 미준수(오답이 아니다)")
        out.append("")

        comp = scorer.compliance(scorable)
        out.append("## 계약 준수")
        out.append("")
        out.append(
            f"채점된 {comp['scored_runs']}런 · 항목 {comp['items']}개 중 "
            f"**{comp['honored']}개가 형식을 지켰다** (미준수 {comp['invalid']}개)."
        )
        out.append("")
        for model, info in sorted(comp["per_model"].items()):
            honored = info["items"] - info["invalid"]
            out.append(
                f"- `{model}` — {info['runs']}런, {honored}/{info['items']} 준수"
            )
        out.append("")
        out.append(
            "준수 실패는 **오답이 아니다**. 미준수가 많으면 모델이 틀린 것이 아니라 "
            "계약 문구를 고쳐야 한다는 뜻이다."
        )
        out.append("")

        out.append("## 이 항목들이 모델을 갈랐나")
        out.append("")
        disc = scorer.discrimination(scorable)
        for item_id, info in disc.items():
            if not info["assessable"]:
                verdict = (
                    f"판단 불가 — 채점된 모델이 {info['models']}개뿐이다 "
                    "(변별은 모델 간 비교에서만 나온다)"
                )
                observed = ", ".join(info["distinct_answers"]) or "없음"
            elif info["distinct_answers"]:
                verdict = (
                    "**변별함**" if info["discriminating"]
                    else f"변별 못 함 — {info['models']}개 모델이 모두 같은 답"
                )
                observed = ", ".join(info["distinct_answers"])
            else:
                verdict = "판단 불가 — 유효한 답이 하나도 없다"
                observed = "없음"
            note = f", 계약 미준수 {info['invalid_runs']}런" if info["invalid_runs"] else ""
            out.append(f"- `{item_id}` — {verdict} (관측된 답: {observed}{note})")
        out.append("")

        stab = scorer.stability(scorable)
        repeated = {m: i for m, i in stab.items() if i["runs"] >= 2}
        if repeated:
            out.append("## 반복 실행 안정성 (같은 모델)")
            out.append("")
            out.append(
                "**통과 수가 같다고 같은 측정이 아니다.** 항목별 답을 대조한다 — "
                "다른 트랙에서 통과 건수가 같은데 통과 항목이 뒤집힌 사례를 겪었다."
            )
            out.append("")
            for model, info in sorted(repeated.items()):
                if info["status"] == "IDENTICAL":
                    out.append(f"- `{model}` — {info['runs']}런 **IDENTICAL** (항목별 답이 전부 같다)")
                else:
                    items = ", ".join(f"`{k}`({'/'.join(v)})" for k, v in info["unstable_items"].items())
                    out.append(f"- `{model}` — {info['runs']}런 **DIVERGED**: {items}")
                if not info.get("decoding_controlled", True):
                    removed = ", ".join(info.get("removed_sampling_params") or []) or "일부"
                    out.append(
                        f"  - 이 백엔드는 `{removed}` 를 거부해 **결정론 제어가 없다**. "
                        "흔들림은 모델 결함이 아니라 구조적 성질이며, "
                        "이 모델의 **단일 런 숫자는 측정이 아니다**."
                    )
            out.append("")

    baseline = scorer.constant_baseline()
    out.append("## 상수 전략 기준선")
    out.append("")
    out.append(
        f"항상 한 라벨만 답하면 {baseline['total_items']}개 중 최대 "
        f"**{baseline['best_constant_passes']}개**를 통과한다"
        f" ({', '.join(baseline['best_constant_labels'])})."
    )
    out.append("이 수보다 조금 나은 결과는 실력의 증거가 아니다.")
    out.append("")

    rejected = [r for r in runs if not r["scorable"]]
    if rejected:
        out.append("## 채점하지 않은 런")
        out.append("")
        for run in rejected:
            out.append(f"- `{run['session']}` — {'; '.join(run['blockers'])}")
        out.append("")

    out.append("## 읽는 법")
    out.append("")
    out.append("- 항목이 5개다. 한 항목이 뒤집히면 '통과 수'가 20% 움직인다.")
    out.append("- 변별 못 한 항목은 이 모델 집합에서 정보를 주지 않는다 — 통과 수를 부풀린다.")
    out.append("- `−` 는 형식을 못 지킨 것이지 틀린 것이 아니다. 둘을 합치면 다른 것을 재게 된다.")
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE_DEFAULT)
    parser.add_argument("--strict", action="store_true", help="채점 불가 런이 있으면 1 로 종료")
    args = parser.parse_args(argv)

    runs, scorer = collect(args.base)
    print(render_markdown(runs, scorer))
    rejected = [r for r in runs if not r["scorable"]]
    if args.strict and rejected:
        print(f"\n[strict] 채점하지 못한 런 {len(rejected)}개", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
