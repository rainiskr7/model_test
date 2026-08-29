"""클레임 등급 — 어떤 수치가 어떤 주장을 달고 나갈 수 있는가.

이 모듈은 **통계 엔진이 아니다.** 이 저장소가 겪은 문제는 분산 추정기가 없어서가
아니라, 이미 측정해 둔 재현성 정보를 발행 게이트가 읽지 않아서였다. 재현성 비교
코드는 트랙마다 있었지만 소비처가 사람이 읽는 보고서뿐이었고, 그래서 1회 실행으로
만든 숫자가 반복 검증된 숫자와 같은 열에 나란히 실렸다.

## 왜 σ 를 추정하지 않는가

k=3~5 로는 표준편차를 쓸 만한 정밀도로 잡을 수 없다. 정규 가정에서도 n=5 의 σ
95% 구간은 대략 ``[0.60s, 2.87s]``, n=3 이면 ``[0.52s, 6.3s]`` 로 자릿수조차
고정되지 않는다. 그런 추정치로 만든 p-value 는 정밀해 보이지만 근거가 없다.

더 결정적인 반례가 이 저장소에 있다. 어떤 모델은 통과 **건수**가 5런 내내 553 으로
같아서 표본표준편차가 0 이었는데, 같은 데이터에서 **통과 항목 10개가 뒤집혔다.**
s=0 을 σ=0 으로 읽으면 그 모델은 "완벽한 재현"으로 발행된다. 합이 안정해 보인
이유는 뒤집힘이 서로 상쇄됐기 때문이다.

**그래서 1급 관측 대상은 스칼라 점수가 아니라 항목별 통과 벡터다.** 건수 범위와
불안정 항목 수는 거기서 파생한다.

## 등급

``snapshot`` (k=1)
    저장·표시·역사 인용은 된다. 순위표 등재와 우열 문장은 안 된다.
    소급 무효화가 아니다 — "이 모델이 이 날짜에 이 숫자를 냈다"는 여전히 참이다.
    다만 **비교의 증거는 아니다.**

``repeatability_observed`` (k>=3, 항목 벡터 보존)
    다수결 점수와 관측된 불안정 예산을 **함께** 표시한다. 두 예산이 겹치지
    않을 때만 "A > B" 를 발행한다.

## comparable() 이 무엇이 아닌지

가설검정이 아니다. 신뢰구간이 아니다. Type I error 를 통제하지 않는다.
**관측된 불안정으로 설명이 끝나는 우열 주장을 거절하는 규칙**일 뿐이다.
이것을 "통계적으로 유의하다"로 부르면 거짓이다. 통과하지 못한 비교는 "두 모델이
같다"는 뜻도 아니다 — 이 반복 횟수로는 판정할 수 없다는 뜻이다.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

__all__ = [
    "SNAPSHOT",
    "REPEATABILITY_OBSERVED",
    "MIN_REPEATS",
    "credential",
    "comparable",
]

SNAPSHOT = "snapshot"
REPEATABILITY_OBSERVED = "repeatability_observed"

# k=2 는 뒤집힘의 존재만 알려주고 다수결을 만들지 못한다(2런에서 1:1 은 다수가
# 없다). 반복성 스크리닝의 최소치를 3 으로 둔다.
MIN_REPEATS = 3


def credential(runs: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """한 코호트(같은 모델·같은 규약)의 반복 런에서 클레임 자격을 만든다.

    ``runs`` 의 각 원소는 ``{"run_id": str, "items": {item_id: bool}}``.
    항목 집합이 런마다 다르면 같은 측정이 아니므로 **교집합만** 쓰고 그 사실을
    남긴다. 조용히 합집합을 쓰면 커버리지 차이가 불안정으로 둔갑한다.
    """

    runs = [dict(run) for run in runs]
    run_ids = [str(run.get("run_id")) for run in runs]
    item_sets = [set((run.get("items") or {}).keys()) for run in runs]

    if not runs:
        return {
            "claim_class": SNAPSHOT, "k": 0, "run_ids": [],
            "reason": "런이 없다",
        }

    shared_items = set.intersection(*item_sets) if item_sets else set()
    dropped = sorted(set().union(*item_sets) - shared_items) if item_sets else []

    passed_sets = [
        {item for item in shared_items if (run.get("items") or {}).get(item)}
        for run in runs
    ]
    pass_counts = [len(s) for s in passed_sets]

    if len(runs) < MIN_REPEATS:
        return {
            "claim_class": SNAPSHOT,
            "k": len(runs),
            "run_ids": run_ids,
            "measured_items": len(shared_items),
            "coverage_dropped": dropped,
            "pass_counts": pass_counts,
            "reason": (
                f"반복 {len(runs)}회 — 반복성을 관측하려면 {MIN_REPEATS}회가 필요하다"
            ),
        }

    unanimous_pass = set.intersection(*passed_sets)
    unanimous_fail = shared_items - set().union(*passed_sets)
    unstable = sorted(shared_items - unanimous_pass - unanimous_fail)

    # 다수결: 과반 런에서 통과한 항목. 점추정을 n=1 보다 안정화할 뿐이고,
    # 비교가 "진짜"라는 증명은 아니다.
    majority = {
        item
        for item in shared_items
        if sum(1 for s in passed_sets if item in s) * 2 > len(runs)
    }

    # 불안정 예산. 뒤집힌 항목이 모두 한쪽으로 몰리면 점수가 그만큼 움직일 수
    # 있다는 **상한**이다. 관측된 건수 범위만 쓰면 위 반례(범위 0, 뒤집힘 10)를
    # 놓치므로, 둘 중 넓은 쪽을 쓴다. 신뢰구간이 아니라 보수적 마진이다.
    center = len(majority)
    envelope = [
        min(center - len(unstable), min(pass_counts)),
        max(center + len(unstable), max(pass_counts)),
    ]

    return {
        "claim_class": REPEATABILITY_OBSERVED,
        "k": len(runs),
        "run_ids": run_ids,
        "measured_items": len(shared_items),
        "coverage_dropped": dropped,
        "pass_counts": pass_counts,
        "count_range": [min(pass_counts), max(pass_counts)],
        "stable_passed": len(unanimous_pass),
        "unstable_items": unstable,
        "majority_passed": center,
        # 이것은 신뢰구간이 아니다. 아래 comparable() 의 주석을 읽을 것.
        "instability_envelope": envelope,
    }


def comparable(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    """두 모델의 우열을 발행해도 되는지.

    **가설검정이 아니다.** 관측된 불안정 예산이 겹치면 그 차이는 이 반복
    횟수로 설명이 끝나므로 우열을 발행하지 않는다. 겹치지 않는다고 "유의하다"는
    뜻이 아니라, **이 데이터로는 반박되지 않는다**는 뜻이다.
    """

    for side, cred in (("left", left), ("right", right)):
        if cred.get("claim_class") != REPEATABILITY_OBSERVED:
            return {
                "comparable": False,
                "reason": (
                    f"{side} 가 `{cred.get('claim_class')}` 이다 — "
                    f"반복 {cred.get('k')}회로는 비교 근거가 없다"
                ),
            }

    if left.get("measured_items") != right.get("measured_items"):
        return {
            "comparable": False,
            "reason": (
                "두 코호트의 채점 항목 수가 다르다 "
                f"({left.get('measured_items')} vs {right.get('measured_items')}) — "
                "커버리지가 다르면 같은 측정이 아니다"
            ),
        }

    lo_l, hi_l = left["instability_envelope"]
    lo_r, hi_r = right["instability_envelope"]
    if lo_l <= hi_r and lo_r <= hi_l:
        return {
            "comparable": False,
            "reason": (
                f"불안정 예산이 겹친다 ({lo_l}–{hi_l} vs {lo_r}–{hi_r}) — "
                "차이가 관측된 흔들림으로 설명된다"
            ),
        }
    return {
        "comparable": True,
        "winner": "left" if lo_l > hi_r else "right",
        "reason": (
            f"불안정 예산이 겹치지 않는다 ({lo_l}–{hi_l} vs {lo_r}–{hi_r}). "
            "통계적 유의성이 아니라, 이 데이터로 반박되지 않는다는 뜻이다"
        ),
    }
