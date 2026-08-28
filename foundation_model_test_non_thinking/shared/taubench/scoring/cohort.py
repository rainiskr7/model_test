"""코호트 키와 재현성 비교.

두 개의 키를 **분리해서** 쓴다. 하나로 합치면 둘 중 하나는 반드시 틀린다.

``comparison_fingerprint`` — 후보 모델을 **제외한** 실행 규약.
    이것이 같아야 서로 다른 모델의 점수를 나란히 놓을 수 있다. 상류 제출 요건도
    "모든 도메인에서 동일한 agent 모델과 사용자 시뮬레이터를 identical arguments 로"
    를 요구한다. 실측으로 겪은 일: 같은 gpt-4.1-mini 사용자 시뮬레이터인데 후보에
    따라 timeout 600s/8192 tokens 와 120s/16384 tokens 로 갈렸다. 후보만 다른 것이
    아니면 그 비교는 모델 비교가 아니다.

``replicate_key`` — comparison_fingerprint + 후보 정체성.
    같은 모델을 같은 규약으로 다시 돌린 것들이다. 재현성은 이 안에서만 논한다.
    후보를 빼먹으면 서로 다른 모델을 서로의 반복 실행으로 오인한다.

재현성 판정이 multimodal 트랙과 다른 이유: 그쪽은 서빙 비결정성 때문에 건수가
흔들려 ``ceil(1% x 분모)`` 허용대가 필요했다. 여기서는 관측된 코호트가 과제 단위로
결정론적이었다 — qwen telecom 을 서로 다른 날 네 번 돌렸는데 통과 과제 **집합**이
완전히 같았다. 따라서 건수 차이가 아니라 **집합 차이**를 보고한다. 다만 이것은 그
규약에서 관측된 사실이지 하네스의 보장이 아니다. 상류는 반복 시행을 전제로 Pass^k
를 정의한다. 집합이 달라지면 실패로 단정하지 않고 차이를 드러낸다.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Iterable, Mapping

__all__ = [
    "comparison_fingerprint",
    "replicate_key",
    "passed_task_ids",
    "reproducibility_report",
]


def _digest(value: Any) -> str:
    material = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def task_set_digest(summary: Mapping[str, Any]) -> str:
    """평가한 과제 **id 집합**의 지문.

    split 이름이 아니라 실제로 고른 id 들이 정체성이다 — 선택 규칙이 바뀌어 다른
    id 를 고르면 지문이 갈린다. 다만 과제 **내용**은 해싱하지 않는다. id 를 유지한
    채 과제 본문이 수정되면 이 지문은 그대로다. 내용 지문은 상류 소스 리비전을
    산출물에 새긴 뒤에 붙일 일이다.
    """

    ids = sorted(str(task_id) for task_id in ((summary.get("split") or {}).get("task_ids") or []))
    return _digest(ids)[:16]


def comparison_fingerprint(summary: Mapping[str, Any]) -> dict[str, Any]:
    """후보를 제외한 실행 규약의 지문.

    후보 모델명, 후보 엔드포인트, 후보의 timeout/max_tokens 는 **넣지 않는다** —
    그것들이 바로 비교 대상이다. 반대로 사용자 시뮬레이터 설정은 넣는다: 후보가
    아니라 실험 조건이므로 달라지면 비교가 성립하지 않는다.
    """

    split = summary.get("split") or {}
    integrity = summary.get("harness_integrity") or {}
    facts = {
        "benchmark": summary.get("benchmark"),
        "scoring_version": summary.get("scoring_version"),
        "domain": split.get("domain"),
        "split_name": split.get("name"),
        "task_set_digest": task_set_digest(summary),
        "official_task_count": split.get("task_count"),
        "runnable_task_count": split.get("runnable_task_count"),
        "mode": integrity.get("mode"),
        "agent_implementation": integrity.get("agent_implementation"),
        "user_implementation": integrity.get("user_implementation"),
        "user_model": integrity.get("user_model_sent_to_litellm"),
        "user_request_timeout": integrity.get("user_request_timeout"),
        "user_max_tokens": integrity.get("user_max_tokens"),
        "max_steps": integrity.get("max_steps"),
        "tau2_version": integrity.get("tau2_version"),
        # 시행 횟수는 측정 대상 자체를 바꾼다. 1회 런의 pass^1 과 4회 런의 pass^1 은
        # 같은 이름의 다른 추정량이고, 재현성 비교에 섞이면 "흔들렸다"와 "다르게
        # 쟀다"를 구분할 수 없다. 기록만 하고 지문에서 빼면 둘이 한 코호트에 들어간다.
        "trials": integrity.get("trials"),
    }
    # 사용자 인자를 기록하지 않는 구버전 산출물은 두 런이 같은 규약이었다는 증거가
    # 없다. 실측: retail 두 런은 둘 다 gpt-4.1-mini 를 썼지만 timeout 600s/8192
    # tokens 와 120s/16384 tokens 로 달랐다.
    #
    # 그렇다고 이것을 **지문에 섞지는 않는다.** 섞으면 같은 모델의 반복 실행끼리도
    # 갈라져 재현성 코호트가 사라진다(실제로 그렇게 만들어봤다가 telecom 반복 4런이
    # 각자 다른 지문이 됐다). 지문은 규약의 정체성이고, 고정 여부는 **비교 자격**이다.
    # 재현성은 여전히 성립하고, 후보 간 비교만 막힌다.
    # 채점기는 관측 결과를 upstream_result_evidence 아래에 넣는다. 위치를 잘못
    # 읽으면 항상 빈 값이 되어, mismatch 가 기록된 산출물도 비교 가능으로 나온다.
    observed = (
        (integrity.get("upstream_result_evidence") or {}).get("user_protocol")
        or integrity.get("user_protocol")
        or {}
    )
    # 불일치가 기록됐으면 선언값이 채워져 있어도 고정된 것이 아니다.
    if observed.get("mismatch"):
        facts["user_protocol_pinned"] = False
        pinned = facts.pop("user_protocol_pinned")
        return {
            "fingerprint": _digest(facts)[:16],
            "facts": facts,
            "user_protocol_pinned": pinned,
            "comparable_across_candidates": pinned,
            "reason": "선언한 사용자 프로토콜과 실제 실행이 다르다",
        }
    facts["user_protocol_pinned"] = bool(observed.get("pinned")) or (
        facts["user_request_timeout"] is not None and facts["user_max_tokens"] is not None
    ) or facts["mode"] == "solo"
    pinned = facts.pop("user_protocol_pinned")
    return {
        "fingerprint": _digest(facts)[:16],
        "facts": facts,
        "user_protocol_pinned": pinned,
        "comparable_across_candidates": pinned,
    }


def replicate_key(summary: Mapping[str, Any]) -> tuple[str, str]:
    """같은 모델을 같은 규약으로 다시 돌린 것을 묶는 키."""

    integrity = summary.get("harness_integrity") or {}
    candidate = str(
        integrity.get("model_sent_to_litellm") or summary.get("model") or "unknown"
    )
    return comparison_fingerprint(summary)["fingerprint"], candidate


def passed_task_ids(summary: Mapping[str, Any], domain: str | None = None) -> set[str]:
    """통과한 과제 id 집합. 건수가 아니라 집합이 재현성의 단위다."""

    domain = domain or (summary.get("split") or {}).get("domain")
    entry = (summary.get("by_domain") or {}).get(str(domain)) or {}
    return {
        str(result.get("task_id"))
        for result in (entry.get("task_results") or [])
        if result.get("passed") is True
    }


def is_multi_trial(summary: Mapping[str, Any], domain: str | None = None) -> bool:
    """한 과제가 여러 번 시행됐는지 — task_id 가 중복되면 다중 시행이다.

    상류는 반복 시행의 과제별 성공 **횟수**로 Pass^k 를 정의한다. 집합으로 접으면
    1/4 통과와 4/4 통과가 똑같이 ``{task_id}`` 가 되어 IDENTICAL 로 보이고, 반대로
    "한 번이라도 통과했는가" 가 확률적으로 흔들린 것을 DIVERGED 로 단정하게 된다.
    둘 다 틀린 판정이므로, 다중 시행 산출물에는 이 비교를 적용하지 않는다.
    """

    domain = domain or (summary.get("split") or {}).get("domain")
    entry = (summary.get("by_domain") or {}).get(str(domain)) or {}
    results = entry.get("task_results") or []
    ids = [str(result.get("task_id")) for result in results]
    return len(ids) != len(set(ids))


def reproducibility_report(summaries: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """복제 키별로 통과 과제 집합을 대조한다."""

    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for summary in summaries:
        grouped[replicate_key(summary)].append(summary)

    report: list[dict[str, Any]] = []
    for (fingerprint, candidate), runs in sorted(grouped.items()):
        sets = [passed_task_ids(run) for run in runs]
        sessions = [str(run.get("session") or run.get("_session") or "?") for run in runs]
        if any(is_multi_trial(run) for run in runs):
            report.append({
                "fingerprint": fingerprint,
                "candidate": candidate,
                "runs": sessions,
                "status": "UNSUPPORTED",
                "reason": "다중 시행 산출물이다 — 통과 집합 비교는 Pass^k 를 대신할 수 없다",
            })
            continue
        if len(runs) < 2:
            report.append({
                "fingerprint": fingerprint,
                "candidate": candidate,
                "runs": sessions,
                "status": "UNVERIFIED",
                "reason": "이 규약으로 이 모델을 한 번만 돌렸다 — 비교 대상이 없다",
            })
            continue
        union, intersection = set().union(*sets), set.intersection(*sets)
        unstable = union - intersection
        report.append({
            "fingerprint": fingerprint,
            "candidate": candidate,
            "runs": sessions,
            "status": "IDENTICAL" if not unstable else "DIVERGED",
            "passed_counts": [len(s) for s in sets],
            "stable_passed": len(intersection),
            "unstable_tasks": sorted(unstable),
            "reason": (
                None
                if not unstable
                else f"통과 과제 집합이 런마다 다르다 ({len(unstable)}건). "
                "건수가 같아도 다른 과제를 맞힌 것이면 같은 측정이 아니다"
            ),
        })
    return report
