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

        out.append("## 이 항목들이 실제로 무엇을 갈랐나")
        out.append("")
        disc = scorer.discrimination(scorable)
        for item_id, info in disc.items():
            if info["distinct_answers"]:
                verdict = "**변별함**" if info["discriminating"] else "변별 못 함 — 모든 런이 같은 답"
                observed = ", ".join(info["distinct_answers"])
            else:
                verdict = "판단 불가 — 유효한 답이 하나도 없다"
                observed = "없음"
            note = f", 계약 미준수 {info['invalid_runs']}런" if info["invalid_runs"] else ""
            out.append(f"- `{item_id}` — {verdict} (관측된 답: {observed}{note})")
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
