#!/usr/bin/env python3
"""발행 게이트를 통과한 KMMLU(harness) 기록을 벤치마크 형식으로 보고한다.

--strict 는 발행 불가 런이 하나라도 있으면 1로 끝난다. `.bad`는 복사본과
미완 런을 모두 뜻할 수 있어 경로만으로 숨기지 않고, 지문 중복일 때만 대표 선택에 쓴다.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

BASE_DEFAULT = Path(__file__).resolve().parent / "foundation_model_test_non_thinking"


def _load_scorer(base: Path):
    path = base / "shared" / "harness" / "scoring" / "score_run.py"
    spec = importlib.util.spec_from_file_location("harness_score_report", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"채점기를 찾을 수 없다: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return module


def collect(base: Path, scorer=None) -> tuple[list[dict[str, Any]], Any]:
    """원본 lm-eval 기록은 건드리지 않고 파생 요약만 수집한다."""

    scorer = scorer or _load_scorer(base)
    expected = scorer.expected_tasks()
    summaries = []
    for run_dir in sorted(base.glob("results/*/*/language/harness")):
        summary = scorer.score_run(run_dir, expected)
        if summary is not None:
            summaries.append(summary)
    return summaries, scorer


def _bad_path(summary: Mapping[str, Any]) -> bool:
    """`.bad`는 지문 중복 그룹에서만 복사본 후보를 뒤로 보내는 표식이다."""

    return any(part.endswith(".bad") for part in str(summary["source_path"]).split("/"))


def dedupe(summaries: list[dict[str, Any]], scorer) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """동일 기록 집계 벡터를 한 대표로 접고 다른 경로를 기록한다.

    지문 일치는 결정적 재실행에서도 생길 수 있으므로 반복 관측이나 분산의 근거로
    사용하지 않는다. 여기서 접는 것은 표시 중복만이다.
    """

    kept: list[dict[str, Any]] = []
    folded: list[dict[str, Any]] = []
    for group in scorer.group_duplicates(summaries).values():
        group = sorted(group, key=lambda summary: (
            _bad_path(summary), len(summary["source_path"]), summary["source_path"],
        ))
        representative = dict(group[0])
        representative["duplicate_paths"] = [summary["source_path"] for summary in group[1:]]
        kept.append(representative)
        folded.extend(group[1:])
    return kept, folded


def _pm(value: float | None, stderr: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.2f}" if stderr is None else f"{value * 100:.2f} ± {stderr * 100:.2f}"


def _claims(base: Path, published: list[dict[str, Any]], scorer):
    """집계값만 남은 런에 claims의 snapshot 비교 규칙을 적용한다."""

    shared = base / "shared"
    sys.path.insert(0, str(shared))
    try:
        from publish.claims import aggregate_credential, comparable
    except Exception as exc:
        # 클레임 등급은 부가 정보다. 그것을 못 읽는다고 수치 보고 전체를 죽이면,
        # 이 스크립트를 쓰지 않고 산출물을 직접 읽는 경로로 되돌아간다 — 이 스크립트가
        # 존재하는 이유가 바로 그 경로를 막는 것이다. 다른 트랙에서 같은 결함을 고쳤다.
        print(f"[report] 클레임 계층을 읽지 못했다: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {}, []
    finally:
        try:
            sys.path.remove(str(shared))
        except ValueError:
            pass
    by_model: dict[str, list[dict[str, Any]]] = {}
    for summary in published:
        by_model.setdefault(summary["model"], []).append(summary)
    credentials = {
        model: aggregate_credential(
            [summary["macro"]["accuracy"] for summary in group], k_runs=len(group)
        )
        for model, group in sorted(by_model.items())
    }
    subject_sets = {
        model: {scorer.subject_set_digest(summary) for summary in group}
        for model, group in by_model.items()
    }
    verdicts = []
    models = sorted(credentials)
    for index, left in enumerate(models):
        for right in models[index + 1:]:
            # comparable()은 개수만 보므로, 같은 수의 다른 과목을 같은 시험으로 통과시키지 않는다.
            if subject_sets[left] != subject_sets[right]:
                verdict = {"comparable": False, "reason": "과목 집합 지문이 다르다 — 같은 개수여도 같은 측정이 아니다"}
            else:
                verdict = comparable(credentials[left], credentials[right])
            verdicts.append((left, right, verdict))
    return credentials, verdicts


def render_markdown(summaries: list[dict[str, Any]], folded: list[dict[str, Any]], scorer, base: Path | None = None) -> str:
    """런 표 다음에 클레임·비교 거부·읽는 법을 같은 순서로 낸다."""

    published = [summary for summary in summaries if summary["publish_status"]["publishable"]]
    rejected = [summary for summary in summaries if not summary["publish_status"]["publishable"]]
    # **프롬프트 프로토콜이 다르면 같은 표에 정렬하지 않는다.** 러너 기본값은
    # `--apply_chat_template` 이고, 채팅 템플릿을 씌운 프롬프트와 raw 프롬프트는
    # 같은 문항이라도 다른 시험이다. 실측: 18런 중 4런이 미적용이며, 그중 2런이
    # 적용 런들과 한 표에 정렬돼 2위·4위를 차지하고 있었다. 커버리지 미달이나
    # n-shot 혼재와 같은 종류의 문제인데 정렬만으로는 드러나지 않는다.
    def _chat_applied(summary):
        values = summary["protocol"].get("chat_template_applied") or []
        return values == [True]

    ordered = sorted(
        [s for s in published if _chat_applied(s)],
        key=lambda summary: -(summary["macro"]["accuracy"] or 0),
    )
    other_protocol = sorted(
        [s for s in published if not _chat_applied(s)],
        key=lambda summary: -(summary["macro"]["accuracy"] or 0),
    )
    out = ["# KMMLU (lm-eval-harness, 5-shot)", ""]
    out.append("**공식 점수는 45과목 5-shot macro 하나다.** 문항가중은 보조 수치이며 KMMLU 점수의 헤드라인·정렬에 쓰지 않는다.")
    out.append("")
    if ordered:
        out.extend([
            "| 모델 | 세션 | KMMLU 5-shot macro (과목 간) | 보조: 문항가중 (문항 표집) | 과목 | 문항 | 재현성 |",
            "|---|---|---|---|---|---|---|",
        ])
        for summary in ordered:
            out.append(
                f"| `{summary['model']}` | `{summary['session']}` | "
                f"{_pm(summary['macro']['accuracy'], summary['macro']['stderr'])} | "
                f"{_pm(summary['micro']['accuracy'], summary['micro']['stderr'])} | "
                f"{summary['macro']['subjects']}/{summary['coverage']['expected_subjects']} | "
                f"{summary['micro']['items']:,} | 미측정 (k=1) |"
            )
        out.extend(["", "macro의 ±는 **과목 간 표준오차**이고 문항가중의 ±는 **문항 표집 이항 표준오차**다. lm-eval `acc_stderr`를 평균한 값이 아니며, 어느 쪽도 재실행 재현성이 아니다.", ""])

        if other_protocol:
            out.append("### 다른 프롬프트 프로토콜로 돌린 런")
            out.append("")
            out.append(
                "아래 런은 `--apply_chat_template` **없이** 돌았다(러너 기본값은 적용). "
                "채팅 템플릿을 씌운 프롬프트와 raw 프롬프트는 같은 문항이라도 다른 "
                "시험이므로 **위 표와 같은 축에 놓을 수 없다.** 무효라는 뜻은 아니다 — "
                "다른 조건의 측정이다."
            )
            out.append("")
            out.extend([
                "| 모델 | 세션 | macro (과목 간) | 보조: 문항가중 | 과목 | 문항 |",
                "|---|---|---|---|---|---|",
            ])
            for summary in other_protocol:
                out.append(
                    f"| `{summary['model']}` | `{summary['session']}` | "
                    f"{_pm(summary['macro']['accuracy'], summary['macro']['stderr'])} | "
                    f"{_pm(summary['micro']['accuracy'], summary['micro']['stderr'])} | "
                    f"{summary['macro']['subjects']}/{summary['coverage']['expected_subjects']} | "
                    f"{summary['micro']['items']:,} |"
                )
            out.append("")

        # 채점기가 경고를 내도 보고가 렌더링하지 않으면 독자에게는 없는 것과 같다.
        # 두 표 모두를 대상으로 한다. 주 표만 보면 다른 프로토콜 런의 경고가
        # 조용히 사라진다.
        warned = [s for s in ordered + other_protocol if s["publish_status"]["warnings"]]
        if warned:
            out.append("### 발행하되 감사할 수 없는 것")
            out.append("")
            out.append(
                "아래 런은 게이트를 통과했지만 프로토콜 기록이 비어 있다. "
                "**기록의 부재는 같음의 증거가 아니다** — 그 항목이 다른 런과 같았는지 "
                "산출물만으로는 확인할 수 없다."
            )
            out.append("")
            for summary in warned:
                out.append(f"- `{summary['model']}` / `{summary['session']}`")
                for warning in summary["publish_status"]["warnings"]:
                    out.append(f"  - {warning}")
            out.append("")
        out.extend(["## 과목별 정확도", "", "45개 과목을 각각 보인다. 이 표에는 발행 게이트를 통과한 런만 있다.", ""])
        out.append("| 과목 | " + " | ".join(f"`{summary['model']}`" for summary in ordered) + " |")
        out.append("|---|" + "---|" * len(ordered))
        for task in scorer.expected_tasks():
            values = []
            for summary in ordered:
                entry = next((entry for entry in summary["by_subject"] if entry["task"] == task), None)
                values.append("—" if entry is None or entry.get("accuracy") is None else f"{entry['accuracy'] * 100:.2f}")
            out.append(f"| `{task}` | " + " | ".join(values) + " |")
        out.append("")
    if folded:
        out.extend(["## 접은 동일 기록 집계 벡터", "", "과목별 정확도와 프로토콜이 같은 경로는 한 줄로 접었다. 이것은 반복 관측이나 분산 0의 증거가 아니다.", ""])
        for summary in folded:
            out.append(f"- `{summary['source_path']}`")
        out.append("")
    if ordered and base is not None:
        credentials, verdicts = _claims(base, ordered, scorer)
        out.extend(["## 클레임 등급", "", "문항별 데이터가 없어 항목 벡터 재현성은 측정하지 않았다. 대표 런은 모델마다 하나여서 모두 `snapshot`이다.", ""])
        for model, credential in credentials.items():
            out.append(f"- `{model}` — `{credential['claim_class']}` (k={credential['k']}) · {credential['reason']}")
        out.extend(["", "## 발행 가능한 우열 주장", ""])
        for left, right, verdict in verdicts:
            if verdict["comparable"]:
                winner = left if verdict["winner"] == "left" else right
                out.append(f"- `{winner}` 우세 — {verdict['reason']}")
            else:
                out.append(f"- `{left}` vs `{right}` — **발행 불가**: {verdict['reason']}")
        out.extend(["", "> 가설검정·신뢰구간·p-value가 아니다. 거절은 두 모델이 같다는 뜻이 아니라, 이 기록으로 우열을 말할 근거가 없다는 뜻이다.", ""])
    if rejected:
        out.extend(["## 발행하지 않은 런", ""])
        for summary in rejected:
            out.append(f"- `{summary['model']}` / `{summary['session']}` — 과목 {summary['coverage']['measured_subjects']}/{summary['coverage']['expected_subjects']}, 문항 {summary['micro']['items']:,}")
            for failure in summary["publish_status"]["failures"]:
                out.append(f"  - {failure}")
            if summary["macro"]["accuracy"] is not None:
                out.append(f"  - 참고 macro {_pm(summary['macro']['accuracy'], summary['macro']['stderr'])} — **위 표와 같은 축에 놓을 수 없다**")
        out.append("")
    out.extend(["## 읽는 법", "", "- 공식 축은 45과목 5-shot macro다. 문항가중은 과목 크기 차이를 드러내는 보조 수치다.", "- 재현성은 미측정이다. 문항 표집 오차는 모델을 다시 실행했을 때의 흔들림이 아니다.", "- 발행 불가 런의 참고 수치는 역사 기록일 뿐, 위 표 수치와 비교하거나 순위를 만들 수 없다."])
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE_DEFAULT)
    parser.add_argument("--write-markdown", type=Path)
    parser.add_argument("--strict", action="store_true", help="발행 불가 런이 있으면 exit 1")
    args = parser.parse_args(argv)
    summaries, scorer = collect(args.base)
    kept, folded = dedupe(summaries, scorer)
    markdown = render_markdown(kept, folded, scorer, args.base)
    if args.write_markdown:
        args.write_markdown.write_text(markdown, encoding="utf-8")
        print(f"wrote {args.write_markdown}")
    else:
        print(markdown)
    rejected = [summary for summary in kept if not summary["publish_status"]["publishable"]]
    if args.strict and rejected:
        print(f"\n[strict] 발행 불가 런 {len(rejected)}개", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
