"""taubench 산출물을 계약이 허용하는 범위에서만 표로 만든다.

이 계층의 존재 이유는 표시가 아니라 **강제**다. 채점기가 새긴 두 플래그는 읽는
코드가 없으면 아무것도 막지 못한다:

``benchmark_eligible``       공식 split 을 다 재지 않은 부분집합인가
``comparable_across_candidates``  사용자 프로토콜이 고정돼 모델 간 비교가 되는가

따라서 여기서는 값을 숨기는 것이 기본이다. 부분집합 점수는 도메인 이름을 달지
못하고, 사용자 프로토콜이 고정되지 않은 런들은 나란히 놓이지 않는다. 실측 근거:
같은 gpt-4.1-mini 사용자 시뮬레이터인데 후보에 따라 timeout 600s/8192 tokens 와
120s/16384 tokens 로 갈렸고, 이 트랙은 사용자 시뮬레이터 교체만으로 같은 모델
점수가 0.475 에서 0.900 으로 뛴 전례가 있다.

도메인을 가로질러 하나의 점수로 합치지 않는다. 상류 리더보드는 retail/airline/
telecom 세 도메인의 단순 평균을 Overall 로 정의하고 셋이 다 있어야 낸다. 우리
산출물은 `test` split 이고 retail 은 40 중 29 만 쟀으므로 그 Overall 이 아니다.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

try:  # 패키지로 임포트될 때 (report_taubench_tracks.py)
    from .cohort import comparison_fingerprint, reproducibility_report
except ImportError:  # 파일 하나만 단독 로드할 때 (테스트 로더)
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cohort import comparison_fingerprint, reproducibility_report

__all__ = ["collect", "render_markdown"]


def collect(base: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """summary.json 을 모은다. 읽을 수 없는 것은 버리지 않고 사유와 함께 남긴다."""

    summaries: list[dict[str, Any]] = []
    unreadable: list[dict[str, str]] = []
    for path in sorted(Path(base).glob("results/*/*/language/taubench/summary.json")):
        try:
            summary = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            unreadable.append({"path": path.as_posix(), "reason": f"{type(exc).__name__}: {exc}"})
            continue
        summary["_session"] = path.parts[-4]
        summary["_path"] = path.as_posix()
        summaries.append(summary)
    return summaries, unreadable


def _domain_entry(summary: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    domain = str((summary.get("split") or {}).get("domain") or "?")
    entry = dict(((summary.get("by_domain") or {}).get(domain)) or {})
    if "benchmark_eligible" not in entry:
        # 옛 채점기가 만든 산출물에는 플래그가 없다. 보고 계층이 재채점을 전제하면
        # 강제가 조용히 풀린다 — 실제로 retail 29/40 이 `retail` 이라는 이름으로
        # 출력됐다. 같은 규칙을 여기서 다시 적용한다.
        split = summary.get("split") or {}
        official, runnable = split.get("task_count"), split.get("runnable_task_count")
        if official and runnable:
            entry["benchmark_eligible"] = int(runnable) == int(official)
            entry.setdefault("coverage", {
                "runnable_task_count": int(runnable),
                "official_task_count": int(official),
                "source": "보고 계층에서 재판정 (산출물에 플래그 없음)",
            })
    return domain, entry


def _axis_name(summary: Mapping[str, Any]) -> str:
    """부분집합에는 도메인 이름을 주지 않는다.

    ``retail`` 과 ``retail/test/judge-free-29`` 는 다른 축이다. 앞의 이름으로
    발행하면 공식 split 성적으로 읽힌다.
    """

    domain, entry = _domain_entry(summary)
    split_name = str((summary.get("split") or {}).get("name") or "?")
    if entry.get("benchmark_eligible") is False:
        coverage = entry.get("coverage") or {}
        runnable = coverage.get("runnable_task_count") or entry.get("runnable_tasks")
        return f"{domain}/{split_name}/judge-free-{runnable}"
    return f"{domain}/{split_name}"


def _score(summary: Mapping[str, Any]) -> str:
    """다중 시행이면 ``pass_rate`` 는 Pass^1 이 아니다.

    ``pass_rate`` 는 시뮬레이션 기준 micro 비율이라 시행을 많이 한 과제에 가중치가
    실린다. Pass^1 은 과제별 성공률의 평균이다. 실측 예: 과제 a 를 3회(2승), b 를
    1회(0승) 돌리면 pass_rate=0.500 이지만 pass^1=0.333 이다. 1회 시행에서만 둘이
    같으므로, 다중 시행에서는 상류 정의인 Pass^k 표를 쓴다.
    """

    _, entry = _domain_entry(summary)
    if not (summary.get("publish_status") or {}).get("publishable", True):
        return "발행 불가"
    table = (entry.get("pass_hat_k") or {}).get("pass_hat_k") or {}
    trials = entry.get("trials") or []
    if trials and trials != [1] and "pass^1" in table:
        tasks = (entry.get("pass_hat_k") or {}).get("tasks")
        return f"{100 * table['pass^1']:.2f} (Pass^1, 과제 {tasks}, 시행 {trials})"
    rate = entry.get("pass_rate")
    if not isinstance(rate, (int, float)):
        return "-"
    passed, measured = entry.get("passed"), entry.get("measured")
    return f"{100 * rate:.2f} ({passed}/{measured})"


def _blockers(summary: Mapping[str, Any]) -> list[str]:
    """이 런이 모델 간 비교에 못 들어가는 이유들."""

    reasons: list[str] = []
    status = summary.get("publish_status") or {}
    if status.get("publishable") is False:
        reasons.append("게이트 거부")
    if not comparison_fingerprint(summary)["comparable_across_candidates"]:
        reasons.append("사용자 프로토콜 미고정")
    _, entry = _domain_entry(summary)
    if entry.get("benchmark_eligible") is False:
        reasons.append("공식 split 부분집합")
    return reasons


def render_markdown(summaries: Iterable[dict[str, Any]], unreadable: list[dict[str, str]]) -> str:
    summaries = list(summaries)
    out: list[str] = [
        "# taubench 트랙 결과",
        "",
        "이 파일은 `report_taubench_tracks.py` 가 `summary.json` 에서 생성한다. 손으로 고치지 말 것.",
        "",
        "읽는 법:",
        "",
        "- **도메인을 가로질러 평균하지 않는다.** 상류 Overall 은 retail/airline/telecom 을",
        "  `base` split 전 과제로 재야 성립한다. 여기 수치는 `test` split 이고 retail 은 부분집합이다.",
        "- 점수는 `Pass^1` 을 100점 척도로 적은 것이다. 괄호는 통과/측정 건수다.",
        "- 부분집합은 도메인 이름을 달지 않는다 (`retail/test/judge-free-29`).",
        "- 사용자 시뮬레이터 프로토콜이 고정되지 않은 런은 모델 간 표에 넣지 않는다.",
        "",
    ]

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for summary in summaries:
        groups[comparison_fingerprint(summary)["fingerprint"]].append(summary)

    out += ["## 비교 코호트", ""]
    for fingerprint, runs in sorted(groups.items()):
        facts = comparison_fingerprint(runs[0])["facts"]
        out += [
            f"### {facts['domain']}/{facts['split_name']} — protocol `{fingerprint}`",
            "",
            f"사용자 시뮬레이터: `{facts['user_model']}` · mode `{facts['mode']}` · tau2 `{facts['tau2_version']}`",
            "",
        ]
        blocked = {id(run): _blockers(run) for run in runs}
        comparable = [run for run in runs if not blocked[id(run)]]
        # 비교 가능한 행이 서로 다른 후보로 둘 이상 있으면 그 부분은 비교가 성립한다.
        # 거부된 런 하나 때문에 코호트 전체에 UNCOMPARABLE 을 붙이면, 멀쩡한 비교까지
        # 읽지 말라고 하는 셈이다 — 실제로 airline 코호트에서 그렇게 나왔다.
        comparable_models = {str(run.get("model")) for run in comparable}
        if len(comparable_models) < 2:
            out += [
                "> **모델 간 비교 불가 (UNCOMPARABLE).** 아래는 개별 런의 관측값이며 "
                "서로 나란히 읽으면 안 된다.",
                "",
            ]
        elif len(comparable) < len(runs):
            out += [
                f"> 비교 가능한 런은 {len(comparable)}개다. 제외 사유가 적힌 행은 "
                "비교에서 빼고 읽을 것.",
                "",
            ]
        out += ["| 모델 | 축 | Pass^1 | 비교 제외 사유 |", "|---|---|---:|---|"]
        for run in sorted(runs, key=lambda item: str(item.get("model"))):
            reasons = ", ".join(blocked[id(run)]) or "—"
            out.append(
                f"| {run.get('model')} | {_axis_name(run)} | {_score(run)} | {reasons} |"
            )
        out.append("")

    out += ["## 재현성", ""]
    checks = reproducibility_report(summaries)
    if not checks:
        out += ["비교할 런이 없습니다.", ""]
    for check in checks:
        label = {
            "IDENTICAL": "**IDENTICAL** — 통과 과제 집합이 완전히 같다",
            "DIVERGED": "**DIVERGED**",
            "UNVERIFIED": "**UNVERIFIED**",
            "UNSUPPORTED": "**UNSUPPORTED**",
        }.get(str(check["status"]), str(check["status"]))
        runs = ", ".join(f"`{session}`" for session in check["runs"])
        out.append(f"- `{check['candidate']}` · protocol `{check['fingerprint']}` — {label}")
        out.append(f"  - 런 {len(check['runs'])}개: {runs}")
        if check.get("passed_counts"):
            out.append(f"  - 통과 건수: {check['passed_counts']}")
        if check.get("unstable_tasks"):
            out.append(f"  - 런마다 달라진 과제 {len(check['unstable_tasks'])}건")
        if check.get("reason"):
            out.append(f"  - {check['reason']}")
    out.append("")

    if unreadable:
        out += ["## 읽을 수 없는 산출물", ""]
        out += [f"- `{item['path']}` — {item['reason']}" for item in unreadable]
        out.append("")
    return "\n".join(out)
