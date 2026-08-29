#!/usr/bin/env python3
"""harness(KMMLU) 결과를 벤치마크 형식으로 낸다.

**100점 만점 한 숫자를 만들지 않는다.** 이 트랙이 재는 것은 45개 과목의 독립된
정확도이고, 하나의 수로 접으면 몇 과목·몇 문항·어느 정도 오차인지가 사라진다.

--strict 는 발행 불가 런이 있으면 1 로 끝난다(CI 용).
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

BASE_DEFAULT = Path(__file__).resolve().parent / "foundation_model_test_non_thinking"


def _load(base: Path, relative: str, name: str):
    path = Path(base) / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"모듈을 찾을 수 없다: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(path.parent))
        except ValueError:
            pass
    return module


def dedupe(base: Path, summaries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """같은 측정이 여러 경로에 복사된 것을 한 줄로 접는다.

    실측: 한 모델의 동일한 수치가 디렉토리 표기(대소문자·접두사)와 ``.bad`` 사본
    때문에 네 줄로 나왔다. 그대로 두면 한 번 잰 것이 네 번 잰 것처럼 보인다.
    대표는 ``.bad`` 가 없고 경로가 짧은 것을 고른다 — multimodal 발행 계약과 같은
    규칙이다.
    """

    scorer = _load(base, "shared/harness/scoring/score_run.py", "harness_score_dedupe")
    kept, folded = [], []
    for _, group in sorted(scorer.group_duplicates(summaries).items()):
        group = sorted(
            group,
            key=lambda s: (".bad" in s["model"] or ".bad" in s["session"],
                           len(s["model"]) + len(s["session"]), s["model"], s["session"]),
        )
        representative = dict(group[0])
        representative["duplicate_paths"] = [
            f"{s['model']}/{s['session']}" for s in group[1:]
        ]
        kept.append(representative)
        folded.extend(group[1:])
    return kept, folded


def collect(base: Path) -> list[dict[str, Any]]:
    scorer = _load(base, "shared/harness/scoring/score_run.py", "harness_score_run")
    expected = scorer.expected_tasks()
    summaries = []
    for run_dir in sorted(Path(base).glob("results/*/*/language/harness")):
        summary = scorer.score_run(run_dir, expected)
        if summary:
            summaries.append(summary)
    return summaries


def _pm(value: float | None, stderr: float | None) -> str:
    if value is None:
        return "—"
    if stderr is None:
        return f"{value * 100:.2f}"
    return f"{value * 100:.2f} ± {stderr * 100:.2f}"


def render_markdown(
    summaries: list[dict[str, Any]],
    folded: list[dict[str, Any]] | None = None,
) -> str:
    publishable = [s for s in summaries if s["publish_status"]["publishable"]]
    rejected = [s for s in summaries if not s["publish_status"]["publishable"]]

    out = ["# KMMLU (lm-eval-harness, 5-shot)", ""]
    out.append(
        "**단일 100점 점수를 내지 않는다.** 45개 과목의 독립된 정확도이고, 하나의 수로 "
        "접으면 몇 과목을 돌렸는지·과목마다 몇 문항이었는지·오차가 얼마인지가 사라진다."
    )
    out.append("")

    if publishable:
        out.append("| 모델 | 세션 | 매크로 (과목 평균) | 마이크로 (문항 평균) | 과목 | 문항 |")
        out.append("|---|---|---|---|---|---|")
        for s in sorted(publishable, key=lambda x: -(x["macro"]["accuracy"] or 0)):
            out.append(
                f"| `{s['model']}` | `{s['session']}` | "
                f"{_pm(s['macro']['accuracy'], s['macro']['stderr'])} | "
                f"{_pm(s['micro']['accuracy'], s['micro']['stderr'])} | "
                f"{s['macro']['subjects']}/{s['coverage']['expected_subjects']} | "
                f"{s['micro']['items']:,} |"
            )
        out.append("")
        out.append(
            "매크로는 **과목**을, 마이크로는 **문항**을 단위로 한 평균이다. 과목별 문항 수가 "
            "다르므로 둘은 갈라지며, 어느 하나가 '진짜'가 아니다. ± 는 **표집 오차**이지 "
            "모델을 다시 돌렸을 때의 재현성이 아니다."
        )
        out.append("")

    if folded:
        out.append("## 접은 중복 산출물")
        out.append("")
        out.append(
            "같은 측정이 여러 경로에 복사돼 있다(디렉토리 대소문자·접두사 차이, `.bad` 사본). "
            "과목별 정확도 벡터가 동일하면 **한 번 잰 것**이므로 한 줄로 접었다. "
            "접지 않으면 그 모델이 여러 번 측정된 것처럼 보인다."
        )
        out.append("")
        for s in folded:
            out.append(f"- `{s['model']}/{s['session']}`")
        out.append("")

    out.append("## 이 표를 읽을 때")
    out.append("")
    out.append(
        "- **재현성은 측정되지 않았다.** 모델마다 런이 하나뿐이라 같은 모델을 다시 돌렸을 때 "
        "점수가 얼마나 움직이는지 이 데이터는 말하지 않는다. 다른 트랙에서는 반복 실행 시 "
        "통과 항목이 뒤집히는 것이 실측됐다."
    )
    out.append(
        "- **매크로의 ± 가 마이크로보다 훨씬 크다.** 과목 간 실력 편차가 문항 표집 오차보다 "
        "크기 때문이며, 정상이다. 작은 쪽만 인용하면 정밀해 보이는 착시가 생긴다."
    )
    out.append("- 순위는 매기지 않는다. 표는 매크로 내림차순으로 정렬돼 있을 뿐이다.")
    out.append("")

    if rejected:
        out.append("## 발행하지 않은 런")
        out.append("")
        for s in rejected:
            out.append(
                f"- `{s['model']}` / `{s['session']}` — 과목 "
                f"{s['coverage']['measured_subjects']}/{s['coverage']['expected_subjects']}, "
                f"문항 {s['micro']['items']:,}"
            )
            for failure in s["publish_status"]["failures"]:
                out.append(f"  - {failure}")
            if s["macro"]["accuracy"] is not None:
                out.append(
                    f"  - (참고: 매크로 {s['macro']['accuracy'] * 100:.2f} — "
                    "**위 표의 값과 같은 축에 놓을 수 없다**)"
                )
        out.append("")
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE_DEFAULT)
    parser.add_argument("--write-markdown", type=Path)
    parser.add_argument("--strict", action="store_true", help="발행 불가 런이 있으면 exit 1")
    args = parser.parse_args(argv)

    summaries, folded = dedupe(args.base, collect(args.base))
    markdown = render_markdown(summaries, folded)
    if args.write_markdown:
        args.write_markdown.write_text(markdown, encoding="utf-8")
        print(f"wrote {args.write_markdown}")
    else:
        print(markdown)
    rejected = [s for s in summaries if not s["publish_status"]["publishable"]]
    if args.strict and rejected:
        print(f"\n[strict] 발행 불가 런 {len(rejected)}개", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
