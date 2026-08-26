"""Read sidecars and render publication-safe Markdown."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .derive import discover_sources
from .schema import (
    PublishStatus,
    apply_model_identity,
    canonical_model_id,
    load_model_identity_map,
    sidecar_path,
    validate_artifact_integrity,
    validate_sidecar,
)
from .select import cohort_key, select_representatives


def _expected_sidecar(source: Path) -> Path:
    return sidecar_path(source.parent, source.stem) if source.suffix == ".jsonl" else sidecar_path(source)


def collect(base: Path, run: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    sidecars: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    identity_mapping = load_model_identity_map(base)
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
            value, _ = apply_model_identity(value, identity_mapping)
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


def _model(sidecar: dict[str, Any]) -> str:
    return canonical_model_id(sidecar)


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
    for sidecar in sorted(cohort, key=_model):
        comparison = sidecar.get("upstream_comparison")
        if isinstance(comparison, dict):
            disagreement = comparison.get("parser_disagreement_rows")
            ours_empty = comparison.get("disagreement_ours_empty")
            different = comparison.get("disagreement_different_choice")
            if isinstance(disagreement, int) and disagreement > 0:
                notes.append(
                    f"> 각주: `{_escape(_model(sidecar))}` — 상류 parser와 {disagreement}행 불일치"
                    f"(우리 무답 {ours_empty}, 다른 선택지 {different}) — 독립 재채점 점수임."
                )
        rate = sidecar.get("no_answer_rate")
        value = rate.get("value") if isinstance(rate, dict) else None
        numerator = rate.get("numerator") if isinstance(rate, dict) else None
        if isinstance(value, (int, float)) and value > 0.10:
            notes.append(
                f"> **주의:** `{_escape(_model(sidecar))}` — 무답 {numerator}건 "
                f"({100 * value:.1f}%). 응답이 지시된 형식을 벗어나 절단됨. "
                "점수를 능력 차이로만 해석하지 말 것."
            )
    return notes


def _selection_metadata(sidecar: dict[str, Any]) -> dict[str, Any]:
    value = sidecar.get("_selection")
    return value if isinstance(value, dict) else {}


def _duplicate_notes(cohort: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    for sidecar in sorted(cohort, key=_model):
        selection = _selection_metadata(sidecar)
        for group in selection.get("folded_duplicates") or []:
            folded = ", ".join(f"`{_escape(path)}`" for path in group.get("folded") or [])
            notes.append(
                f"> 중복 접기: `{_escape(_model(sidecar))}` — `{_escape(group.get('kept'))}` 유지; "
                f"동일 artifact role/SHA-256·측정 payload 복사본 {folded} 접음."
            )
        undated = selection.get("undated_candidates") or []
        if undated:
            units = ", ".join(
                f"`{_escape((run.get('source') or {}).get('unit'))}`" for run in undated
            )
            notes.append(
                f"> 대표 자격 제외: `{_escape(_model(sidecar))}` — 완료 시각이 없어 최신임을 "
                f"보일 수 없는 런 {units}. 재현성 산포에는 그대로 포함된다."
            )
    return notes


# A run with no completion time sorts before every dated run.  ``datetime.min``
# must stay in UTC: ``astimezone()`` on it raises "year 0 is out of range" west
# of Greenwich, which is where an undated legacy run first reaches this sort.
_UNDATED = datetime.min.replace(tzinfo=timezone.utc)


def _completed_sort_key(sidecar: dict[str, Any]) -> tuple[datetime, str]:
    raw = sidecar.get("completed_at_utc")
    try:
        stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        stamp = _UNDATED
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp, str((sidecar.get("source") or {}).get("unit"))


def _repro_axis(sidecar: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    axis = _headline_axis(sidecar)
    if not isinstance(axis, dict):
        return None, "overall/rubric 비교 축이 없음"
    unit = axis.get("unit")
    if unit == "fraction":
        if (
            isinstance(axis.get("numerator"), bool)
            or not isinstance(axis.get("numerator"), int)
            or isinstance(axis.get("denominator"), bool)
            or not isinstance(axis.get("denominator"), int)
            or axis["denominator"] <= 0
        ):
            return axis, "fraction 축의 분자/분모가 유효하지 않음"
        return axis, None
    if unit == "score/10":
        if (
            isinstance(axis.get("value"), bool)
            or not isinstance(axis.get("value"), (int, float))
            or not 0 <= axis["value"] <= 10
            or isinstance(axis.get("denominator"), bool)
            or not isinstance(axis.get("denominator"), int)
            or axis["denominator"] <= 0
        ):
            return axis, "score/10 축의 평균/분모가 유효하지 않음"
        return axis, None
    return axis, f"지원하지 않는 재현성 비교 단위: {unit!r}"


def reproducibility_checks(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compare the full spread of exact-run-distinct cohort candidates."""

    checks: list[dict[str, Any]] = []
    for representative in selected:
        if representative.get("benchmark_id") == "B4-latency-profile":
            continue
        runs = list(_selection_metadata(representative).get("cohort_runs") or [])
        if len(runs) < 2:
            continue
        runs.sort(key=_completed_sort_key)
        axis_results = [_repro_axis(run) for run in runs]
        axes = [item[0] for item in axis_results]
        reasons = [item[1] for item in axis_results if item[1]]
        units = {axis.get("unit") for axis in axes if isinstance(axis, dict)}
        if reasons or len(units) != 1:
            if len(units) != 1:
                reasons.append(f"비교 축 단위가 일치하지 않음: {sorted(map(str, units))}")
            checks.append({
                "representative": representative,
                "runs": runs,
                "axes": axes,
                "comparable": False,
                "reason": "; ".join(dict.fromkeys(reasons)),
                "passed": False,
            })
            continue
        typed_axes = [axis for axis in axes if isinstance(axis, dict)]
        unit = next(iter(units))
        denominators = {axis["denominator"] for axis in typed_axes}
        if len(denominators) != 1:
            checks.append({
                "representative": representative,
                "runs": runs,
                "axes": axes,
                "comparable": False,
                "reason": f"같은 protocol cohort의 분모가 다름: {sorted(denominators)}",
                "passed": False,
            })
            continue
        denominator = next(iter(denominators))
        if unit == "fraction":
            numerators = [axis["numerator"] for axis in typed_axes]
            spread = max(numerators) - min(numerators)
            tolerance = math.ceil(0.01 * denominator)
            checks.append({
                "representative": representative,
                "runs": runs,
                "axes": axes,
                "comparable": True,
                "comparator": "fraction",
                "spread": spread,
                "spread_pp": 100 * spread / denominator,
                "tolerance": tolerance,
                "passed": spread <= tolerance,
            })
        elif unit == "score/10":
            averages = [float(axis["value"]) for axis in typed_axes]
            spread = max(averages) - min(averages)
            tolerance = 0.10
            checks.append({
                "representative": representative,
                "runs": runs,
                "axes": axes,
                "comparable": True,
                "comparator": "score/10",
                "spread": spread,
                "spread_pp": 100 * spread / 10,
                "tolerance": tolerance,
                "passed": spread <= tolerance + 1e-12,
            })
    return checks


def _reproducibility_notes(cohort: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    for representative in cohort:
        # A cohort of one cannot be compared with anything.  Saying so beats an
        # absent line: silence reads the same as "checked and fine".  B4 latency
        # has no validated tolerance policy at all, so it is out of scope here
        # rather than merely unverified.
        if representative.get("benchmark_id") == "B4-latency-profile":
            continue
        runs = _selection_metadata(representative).get("cohort_runs") or []
        if len(runs) < 2:
            notes.append(
                f"> 재현성: `{_escape(_model(representative))}` — 이 코호트에 런 1개. "
                f"비교 대상 없음 — **UNVERIFIED**(발행은 유지; 산출물·채점 계약은 유효)"
            )
    for check in reproducibility_checks(cohort):
        representative = check["representative"]
        result = "PASS" if check["passed"] else "FAIL"
        if not check.get("comparable"):
            notes.append(
                f"> 재현성: `{_escape(_model(representative))}` — 이 코호트에 런 {len(check['runs'])}개. "
                f"비교 불가 — **FAIL**"
            )
            notes.append(f">   **사유:** {_escape(check.get('reason'))}")
        elif check.get("comparator") == "fraction":
            notes.append(
                f"> 재현성: `{_escape(_model(representative))}` — 이 코호트에 런 {len(check['runs'])}개. "
                f"코호트 산포 {check['spread']}건 ({check['spread_pp']:.2f}%p), "
                f"허용 {check['tolerance']}건 — **{result}**"
            )
        else:
            notes.append(
                f"> 재현성: `{_escape(_model(representative))}` — 이 코호트에 런 {len(check['runs'])}개. "
                f"평균 점수 산포 {check['spread']:.3f}/10 (전체 척도 {check['spread_pp']:.2f}%p), "
                f"허용 {check['tolerance']:.2f}/10 — **{result}**"
            )
        for index, (run, axis) in enumerate(zip(check["runs"], check["axes"])):
            labels = []
            if index == 0:
                labels.append("기준")
            if run is representative or (run.get("source") or {}).get("unit") == (representative.get("source") or {}).get("unit"):
                labels.append("대표")
            suffix = f" ({', '.join(labels)})" if labels else ""
            notes.append(
                f">   `{_escape(run.get('session'))}`  "
                f"{_escape(_metric(axis) if isinstance(axis, dict) else '비교 축 없음')}{suffix}"
            )
        notes.extend(_inference_caveats(check["runs"]))
        notes.extend(_judge_drift_notes(check["runs"]))
    return notes


def _judge_drift_notes(runs: list[dict[str, Any]]) -> list[str]:
    """Catch a judge whose prompt text moved under a stable version string.

    The template hash is deliberately not part of the fingerprint: making it so
    would fork the cohort away from every run recorded before the field existed.
    Within a cohort it is still decisive — two runs judged by different prompt
    text are not repeats of one measurement.
    """

    def _recorded(run, key):
        return ((run.get("protocol") or {}).get("recorded") or {}).get(key)

    hashes = {
        str(_recorded(run, "judge_prompt_template_sha256"))
        for run in runs
        if _recorded(run, "judge_prompt_template_sha256")
    }
    if len(hashes) < 2:
        return []
    return [
        "> **경고:** 이 코호트의 판정 프롬프트 템플릿 해시가 서로 다르다 "
        f"({', '.join(f'`{value[7:19]}`' for value in sorted(hashes))}). "
        "`judge_prompt_version` 은 같은데 본문이 바뀌었다는 뜻이므로 "
        "두 런은 같은 측정의 반복이 아니다."
    ]


def _inference_caveats(runs: list[dict[str, Any]]) -> list[str]:
    """Name the protocol facts a cohort agreed on by inference rather than record.

    Two runs share a cohort when their effective protocol matches, and an
    inferred value counts toward that match.  Inference restores a runner
    convention (KRETA direct defaults to ``KRETA_MAX_TOKENS=32``), but the
    runner also honours an environment override, so the artifact does not prove
    the value.  A spread computed across such a cohort is evidence about the
    server, not proof that both runs sent the same request — say so.
    """

    caveats: list[str] = []
    for run in runs:
        protocol = run.get("protocol") or {}
        inferred = protocol.get("inferred") or {}
        if not isinstance(inferred, dict) or not inferred:
            continue
        # A key the artifact also records is not an inference, even when an
        # inferred duplicate agrees with it.  Naming it would state the opposite
        # of what the sidecar shows.
        recorded = protocol.get("recorded") or {}
        names = [key for key in sorted(inferred) if key not in recorded]
        if not names:
            continue
        keys = ", ".join(f"`{_escape(key)}`" for key in names)
        caveats.append(
            f">   **주의:** `{_escape(run.get('session'))}` 의 {keys} 는 산출물에 기록된 값이 "
            f"아니라 러너 규약에서 복원한 추론값이다. 요청 규약이 같았다는 증명은 아니다."
        )
    return caveats


def _unmapped_identity_names(sidecars: list[dict[str, Any]]) -> list[str]:
    names = {
        str(sidecar.get("model"))
        for sidecar in sidecars
        if isinstance(sidecar.get("model_identity"), dict)
        and sidecar["model_identity"].get("mapped") is False
    }
    return sorted(names)


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
                _model(item[0]),
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
                    f"| {_escape(_model(sidecar))} | {_escape(_metric(axis))} | "
                    f"{_no_answer_percent(sidecar)} | {_escape(_state(sidecar))} |"
                )
            else:
                out.append(
                    f"| {_escape(_model(sidecar))} | {_escape(_metric(axis))} | {_escape(_state(sidecar))} |"
                )
        out.append("")
        provenance_cohort = provenance_by_cohort.get((benchmark, variant, fingerprint), cohort)
        if note := _dataset_commit_note(provenance_cohort):
            out.extend([note, ""])
        if benchmark == "KRETA":
            notes = _kreta_notes(cohort)
            if notes:
                out.extend(notes + [""])
        selection_notes = _duplicate_notes(cohort) + _reproducibility_notes(cohort)
        if selection_notes:
            out.extend(selection_notes + [""])


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
                    rows.append((_model(sidecar), str(axis.get("name")), sidecar, axis))
        for _, _, sidecar, axis in sorted(rows):
            out.append(
                f"| {_escape(_model(sidecar))} | {_escape(axis.get('name'))} | "
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
            rows.append((_model(sidecar), condition, sidecar, metrics))
    out.extend([
        "| 모델 | condition | TTFT | total | tokens/sec | 상태 |",
        "|---|---|---:|---:|---:|---|",
    ])
    for _, condition, sidecar, metrics in sorted(rows):
        out.append(
            f"| {_escape(_model(sidecar))} | {_escape(condition)} | "
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
        selection_notes = _duplicate_notes(cohort)
        if selection_notes:
            out.extend(selection_notes + [""])


def render_markdown(
    sidecars: list[dict[str, Any]],
    missing: list[dict[str, str]],
    comparison_sidecars: list[dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    publishable = [sidecar for sidecar in sidecars if sidecar.get("publishable")]
    selection_sources = publishable
    if comparison_sidecars is not None:
        scope_keys = {cohort_key(sidecar) for sidecar in publishable}
        selection_sources = [
            sidecar for sidecar in comparison_sidecars
            if sidecar.get("publishable") and cohort_key(sidecar) in scope_keys
        ]
    selected, ambiguous = select_representatives(selection_sources)
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
    unmapped = _unmapped_identity_names(sidecars + selection_sources)
    if unmapped:
        out.extend([
            "## 모델 정체성 경고",
            "",
            "다음 서빙명은 `configs/model_identity.json`에 미매핑이다. 추측해서 합치지 않고 자기 이름을 canonical id로 사용한다.",
            "",
            *(f"- `{_escape(name)}`" for name in unmapped),
            "",
        ])
    _headline(out, selected, selection_sources)
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
            for group in item.get("folded_duplicates") or []:
                out.append(
                    f"  - 동일 artifact role/SHA-256·측정 payload 복사본 접음; "
                    f"유지: `{_escape(group['kept'])}`"
                )
                for folded in group.get("folded") or []:
                    out.append(f"    - 접음: `{_escape(folded)}`")

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
    comparison_sidecars: list[dict[str, Any]] | None = None,
) -> bool:
    blocking = [
        sidecar for sidecar in sidecars
        if not (
            sidecar.get("status") in {PublishStatus.NATIVE.value, PublishStatus.LEGACY_REVALIDATED.value}
            or (
                sidecar.get("status") == PublishStatus.UNSCORED.value
                and sidecar.get("benchmark_id") == "KOFFVQA"
                and sidecar.get("variant") == "generation"
            )
        )
    ]
    comparison = comparison_sidecars if comparison_sidecars is not None else sidecars
    scope_keys = {cohort_key(sidecar) for sidecar in sidecars if sidecar.get("publishable")}
    comparison_selected, comparison_ambiguous = select_representatives(comparison)
    relevant_selected = [item for item in comparison_selected if cohort_key(item) in scope_keys]
    relevant_ambiguous = [item for item in comparison_ambiguous if item["key"] in scope_keys]
    reproduction_failed = any(not check["passed"] for check in reproducibility_checks(relevant_selected))
    return bool(blocking or missing or ambiguous or relevant_ambiguous or reproduction_failed)
