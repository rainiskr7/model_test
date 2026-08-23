"""Read sidecars and render publication-safe Markdown."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .derive import discover_sources
from .schema import PublishStatus, sidecar_path, validate_artifact_integrity, validate_sidecar
from .select import select_representatives


def _expected_sidecar(source: Path) -> Path:
    return sidecar_path(source.parent, source.stem) if source.suffix == ".jsonl" else sidecar_path(source)


def collect(base: Path, run: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    sidecars: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for source in discover_sources(base):
        path = _expected_sidecar(source)
        if run is not None:
            try:
                parts = source.relative_to(base / "results").parts
                if len(parts) < 2 or parts[1] != run:
                    continue
            except ValueError:
                continue
        if not path.exists():
            missing.append({"source": source.relative_to(base).as_posix(), "reason": "게이트 기록 없음"})
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            validate_sidecar(value)
            validate_artifact_integrity(value, base)
        except Exception as exc:
            missing.append({
                "source": source.relative_to(base).as_posix(),
                "reason": f"게이트 기록 손상: {type(exc).__name__}: {exc}",
            })
            continue
        sidecars.append(value)
    return sidecars, missing


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _metric(axis: dict[str, Any]) -> str:
    unit = axis.get("unit")
    value = axis.get("value")
    numerator, denominator = axis.get("numerator"), axis.get("denominator")
    if unit == "fraction" and isinstance(numerator, int) and isinstance(denominator, int) and denominator:
        return f"{numerator}/{denominator} = {100 * numerator / denominator:.2f}%"
    if unit == "score/10" and isinstance(value, (int, float)):
        return f"{value:.2f}/10"
    if unit == "seconds" and isinstance(value, (int, float)):
        return f"{value:.3f}s"
    if unit == "tokens/second" and isinstance(value, (int, float)):
        return f"{value:.2f} tokens/s"
    if isinstance(value, (int, float)):
        return f"{value:g} {unit or ''}".strip()
    return "-"


HEADLINE_ORDER = {
    "KRETA": 0,
    "K-MMBench": 1,
    "K-DTCBench": 2,
    "MTVQA-KR": 3,
    "KOFFVQA-judge": 4,
    "B3-structured-output": 5,
}


def _state(sidecar: dict[str, Any]) -> str:
    if sidecar.get("provisional"):
        return "PROVISIONAL — 판정기 기준, 인간 검증 없음"
    return str(sidecar["status"])


def _headline_axis(sidecar: dict[str, Any]) -> dict[str, Any] | None:
    if sidecar.get("benchmark_id") == "B4-latency-profile":
        return None
    axes = (sidecar.get("metrics") or {}).get("axes") or []
    return next((axis for axis in axes if axis.get("name") in {"overall", "rubric"}), None)


def _display_cohorts(sidecars: list[dict[str, Any]]) -> list[tuple[tuple[str, str, str], list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for sidecar in sidecars:
        protocol = sidecar.get("protocol") or {}
        grouped[(str(sidecar.get("benchmark_id")), str(sidecar.get("variant")), str(protocol.get("fingerprint")))].append(sidecar)
    return sorted(
        grouped.items(),
        key=lambda item: (
            HEADLINE_ORDER.get(item[0][0], 99),
            item[0][0],
            item[0][1],
            item[0][2],
        ),
    )


def _cohort_heading(benchmark: str, variant: str, fingerprint: str, denominator: Any = None) -> str:
    count = f", {denominator}문항" if isinstance(denominator, int) and denominator > 0 else ""
    short = fingerprint.removeprefix("sha256:")[:12]
    return f"{benchmark} — {variant}{count} — protocol `{short}`"


def _dataset_commit_note(cohort: list[dict[str, Any]]) -> str | None:
    commits = {
        provenance.get("git_commit")
        for sidecar in cohort
        if isinstance(
            provenance := (sidecar.get("protocol") or {}).get("recorded", {}).get("dataset_provenance"),
            dict,
        )
        and provenance.get("git_commit")
    }
    if len(commits) < 2:
        return None
    short = ", ".join(f"`{commit[:12]}`" for commit in sorted(commits))
    return f"> 각주: 기록된 repo commit이 런마다 다름(문항 집합은 동일): {short}."


def _no_answer_percent(sidecar: dict[str, Any]) -> str:
    rate = sidecar.get("no_answer_rate")
    value = rate.get("value") if isinstance(rate, dict) else None
    return f"{100 * value:.1f}%" if isinstance(value, (int, float)) else "-"


def _kreta_notes(cohort: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    for sidecar in sorted(cohort, key=lambda item: str(item.get("model"))):
        comparison = sidecar.get("upstream_comparison")
        if isinstance(comparison, dict):
            disagreement = comparison.get("parser_disagreement_rows")
            ours_empty = comparison.get("disagreement_ours_empty")
            different = comparison.get("disagreement_different_choice")
            if isinstance(disagreement, int) and disagreement > 0:
                notes.append(
                    f"> 각주: `{_escape(sidecar.get('model'))}` — 상류 parser와 {disagreement}행 불일치"
                    f"(우리 무답 {ours_empty}, 다른 선택지 {different}) — 독립 재채점 점수임."
                )
        rate = sidecar.get("no_answer_rate")
        value = rate.get("value") if isinstance(rate, dict) else None
        numerator = rate.get("numerator") if isinstance(rate, dict) else None
        if isinstance(value, (int, float)) and value > 0.10:
            notes.append(
                f"> **주의:** `{_escape(sidecar.get('model'))}` — 무답 {numerator}건 "
                f"({100 * value:.1f}%). 응답이 지시된 형식을 벗어나 절단됨. "
                "점수를 능력 차이로만 해석하지 말 것."
            )
    return notes


def _headline(
    out: list[str],
    selected: list[dict[str, Any]],
    provenance_sources: list[dict[str, Any]] | None = None,
) -> None:
    out.extend(["## 헤드라인 — 벤치마크별 overall", ""])
    headline = [sidecar for sidecar in selected if _headline_axis(sidecar) is not None]
    provenance_by_cohort = dict(_display_cohorts(provenance_sources or selected))
    if not headline:
        out.extend(["발행 가능한 overall 수치가 없습니다.", ""])
        return
    for (benchmark, variant, fingerprint), cohort in _display_cohorts(headline):
        rows = [(sidecar, _headline_axis(sidecar)) for sidecar in cohort]
        rows = [(sidecar, axis) for sidecar, axis in rows if axis is not None]
        rows.sort(
            key=lambda item: (
                -(item[1].get("value") if isinstance(item[1].get("value"), (int, float)) else float("-inf")),
                str(item[0].get("model")),
            )
        )
        denominator = rows[0][1].get("denominator") if rows else None
        header = (
            ["| 모델 | 결과 | 무답률 | 상태 |", "|---|---|---:|---|"]
            if benchmark == "KRETA"
            else ["| 모델 | 결과 | 상태 |", "|---|---|---|"]
        )
        out.extend([
            f"### {_cohort_heading(benchmark, variant, fingerprint, denominator)}",
            "",
            f"전체 protocol fingerprint: `{fingerprint}`",
            "",
            *header,
        ])
        for sidecar, axis in rows:
            if benchmark == "KRETA":
                out.append(
                    f"| {_escape(sidecar.get('model'))} | {_escape(_metric(axis))} | "
                    f"{_no_answer_percent(sidecar)} | {_escape(_state(sidecar))} |"
                )
            else:
                out.append(
                    f"| {_escape(sidecar.get('model'))} | {_escape(_metric(axis))} | {_escape(_state(sidecar))} |"
                )
        out.append("")
        provenance_cohort = provenance_by_cohort.get((benchmark, variant, fingerprint), cohort)
        if note := _dataset_commit_note(provenance_cohort):
            out.extend([note, ""])
        if benchmark == "KRETA":
            notes = _kreta_notes(cohort)
            if notes:
                out.extend(notes + [""])


def _detail_axes(out: list[str], selected: list[dict[str, Any]]) -> None:
    out.extend(["## 세부 축", "", "카테고리 및 System1/2 등 세부 축은 벤치별로 접어 두었다.", ""])
    detail_sources = [
        sidecar for sidecar in selected
        if sidecar.get("benchmark_id") != "B4-latency-profile"
        and any(axis.get("name") not in {"overall", "rubric"} for axis in (sidecar.get("metrics") or {}).get("axes") or [])
    ]
    if not detail_sources:
        out.extend(["세부 축이 없습니다.", ""])
        return
    for (benchmark, variant, fingerprint), cohort in _display_cohorts(detail_sources):
        out.extend([
            "<details>",
            f"<summary>{_escape(_cohort_heading(benchmark, variant, fingerprint))}</summary>",
            "",
            f"전체 protocol fingerprint: `{fingerprint}`",
            "",
            "| 모델 | 축 | 결과 | 상태 |",
            "|---|---|---|---|",
        ])
        rows = []
        for sidecar in cohort:
            for axis in (sidecar.get("metrics") or {}).get("axes") or []:
                if axis.get("name") not in {"overall", "rubric"}:
                    rows.append((str(sidecar.get("model")), str(axis.get("name")), sidecar, axis))
        for _, _, sidecar, axis in sorted(rows):
            out.append(
                f"| {_escape(sidecar.get('model'))} | {_escape(axis.get('name'))} | "
                f"{_escape(_metric(axis))} | {_escape(_state(sidecar))} |"
            )
        out.extend(["", "</details>", ""])


def _latency_table(out: list[str], cohort: list[dict[str, Any]], percentile: str) -> None:
    rows: list[tuple[str, str, dict[str, Any], dict[str, dict[str, Any]]]] = []
    for sidecar in cohort:
        values: dict[str, dict[str, Any]] = defaultdict(dict)
        for axis in (sidecar.get("metrics") or {}).get("axes") or []:
            parts = str(axis.get("name")).rsplit(":", 2)
            if len(parts) == 3 and parts[2] == percentile:
                condition, metric, _ = parts
                values[condition][metric] = axis
        for condition, metrics in values.items():
            rows.append((str(sidecar.get("model")), condition, sidecar, metrics))
    out.extend([
        "| 모델 | condition | TTFT | total | tokens/sec | 상태 |",
        "|---|---|---:|---:|---:|---|",
    ])
    for _, condition, sidecar, metrics in sorted(rows):
        out.append(
            f"| {_escape(sidecar.get('model'))} | {_escape(condition)} | "
            f"{_escape(_metric(metrics.get('ttft') or {}))} | "
            f"{_escape(_metric(metrics.get('total') or {}))} | "
            f"{_escape(_metric(metrics.get('tokens_per_sec') or {}))} | {_escape(_state(sidecar))} |"
        )


def _latency(out: list[str], selected: list[dict[str, Any]]) -> None:
    out.extend(["## B4 지연시간 — 운영 지표", "", "정확도 헤드라인과 분리한다. 기본 표는 p50만 표시한다.", ""])
    sources = [sidecar for sidecar in selected if sidecar.get("benchmark_id") == "B4-latency-profile"]
    if not sources:
        out.extend(["발행 가능한 B4 지연시간이 없습니다.", ""])
        return
    for (benchmark, variant, fingerprint), cohort in _display_cohorts(sources):
        out.extend([
            f"### {_cohort_heading(benchmark, variant, fingerprint)}",
            "",
            f"전체 protocol fingerprint: `{fingerprint}`",
            "",
            "#### p50",
            "",
        ])
        _latency_table(out, cohort, "p50")
        out.extend([
            "",
            "<details>",
            "<summary>p95 / p99 보기</summary>",
            "",
            "#### p95",
            "",
        ])
        _latency_table(out, cohort, "p95")
        out.extend(["", "#### p99", ""])
        _latency_table(out, cohort, "p99")
        out.extend(["", "</details>", ""])


def render_markdown(
    sidecars: list[dict[str, Any]],
    missing: list[dict[str, str]],
) -> tuple[str, list[dict[str, Any]]]:
    selected, ambiguous = select_representatives(sidecars)
    publishable = [sidecar for sidecar in sidecars if sidecar.get("publishable")]
    blocked = [sidecar for sidecar in sidecars if not sidecar.get("publishable")]
    status_counts = Counter(sidecar.get("status") for sidecar in sidecars)
    out = [
        "# multimodal 트랙 결과",
        "",
        "이 파일은 `report_multimodal_tracks.py`가 `_derived` sidecar에서 생성한다. 손으로 고치지 말 것.",
        "",
        "판단 기준: [`MULTIMODAL_PUBLISH_CONTRACT.md`](MULTIMODAL_PUBLISH_CONTRACT.md).",
        "",
        f"발행 가능 source **{len(publishable)}** / 발행 불가 source **{len(blocked)}** / 게이트 기록 없음 **{len(missing)}**.",
        "",
        "읽는 법:",
        "",
        "- 서로 다른 벤치와 축을 합산하거나 평균하지 않는다.",
        "- 결과는 반올림된 점수만 보지 말고 분자/분모를 함께 본다.",
        "- PROVISIONAL은 판정기 기준이며 인간 검증 전이다.",
        "- 거부된 런의 숫자는 원본에 존재하더라도 인용하지 않는다.",
        "",
    ]
    _headline(out, selected, publishable)
    out.extend(["## 상태 요약", "", "| 상태 | source 수 |", "|---|---:|"])
    for status in PublishStatus:
        out.append(f"| {status.value} | {status_counts.get(status.value, 0)} |")
    out.append("")
    _detail_axes(out, selected)
    inferred_rows = [sidecar for sidecar in selected if (sidecar.get("protocol") or {}).get("inferred")]
    if inferred_rows:
        out.extend(["", "### 추론 복원 provenance", ""])
        for sidecar in inferred_rows:
            facts = json.dumps(sidecar["protocol"]["inferred"], ensure_ascii=False, sort_keys=True)
            out.append(f"- `{_escape(sidecar['source']['unit'])}`: `{_escape(facts)}`")

    if ambiguous:
        out.extend(["", "## 대표 런 자동 선정 불가 — 수치 비노출", ""])
        for item in ambiguous:
            benchmark, variant, _, model = item["key"]
            out.append(f"- **{_escape(benchmark)} / {_escape(variant)} / {_escape(model)}** — {_escape(item['reason'])}")
            for candidate in item["candidates"]:
                out.append(f"  - `{_escape(candidate['source']['unit'])}`")

    if blocked:
        out.extend(["", "## 발행 불가 — 점수를 인용하지 마십시오", ""])
        for sidecar in sorted(blocked, key=lambda item: item["source"]["unit"]):
            out.append(
                f"- **{_escape(sidecar.get('benchmark_id'))} / {_escape(sidecar.get('model'))} / "
                f"{_escape(sidecar.get('session'))}** — `{_escape(sidecar.get('status'))}`"
            )
            reasons = sidecar.get("failures") or (["채점 산출물 없음"] if sidecar.get("status") == "UNSCORED" else ["발행 게이트 미통과"])
            for reason in reasons:
                out.append(f"  - {_escape(reason)}")
    if missing:
        out.extend(["", "## 게이트 기록 없음 — 수치 비노출", ""])
        for item in sorted(missing, key=lambda value: value["source"]):
            out.append(f"- `{_escape(item['source'])}` — {_escape(item['reason'])}")
    out.append("")
    _latency(out, selected)
    return "\n".join(out), ambiguous


def strict_failed(
    sidecars: list[dict[str, Any]],
    missing: list[dict[str, str]],
    ambiguous: list[dict[str, Any]],
) -> bool:
    blocking = [
        sidecar for sidecar in sidecars
        if sidecar.get("status") not in {PublishStatus.NATIVE.value, PublishStatus.LEGACY_REVALIDATED.value, PublishStatus.UNSCORED.value}
    ]
    return bool(blocking or missing or ambiguous)
