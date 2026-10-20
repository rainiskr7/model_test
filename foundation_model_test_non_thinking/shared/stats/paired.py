"""입력: 두 모델의 반복 평균 문항 점수·seed·재표집 횟수. 출력: paired cluster CI(순수)."""

from math import fsum
import random

from shared.stats.item_scores import index_items

INTERPRETATION = "관측한 반복 평균에 조건부인 문항 표집 불확실성"


def validate_pair(a, b):
    """두 모델의 코호트·지표·반복 수·문항 및 이미지 집합 일치를 검사한다."""
    if not a.get("cohort") or a["cohort"] != b.get("cohort"):
        raise ValueError("cohort mismatch")
    if not a.get("metric") or any(a.get(k) != b.get(k) for k in ("metric", "version", "upstream")):
        raise ValueError("metric mismatch")
    if type(a.get("repetitions")) is not int or a["repetitions"] < 1:
        raise ValueError("invalid repetition count")
    if type(b.get("repetitions")) is not int or a["repetitions"] != b["repetitions"]:
        raise ValueError("repetition count mismatch")
    left, right = index_items(a["items"]), index_items(b["items"])
    if left.keys() != right.keys():
        raise ValueError("item set mismatch; intersection-only comparison forbidden")
    if any(left[k]["cluster"] != right[k]["cluster"] for k in left):
        raise ValueError("image cluster mismatch")
    return left, right


def percentile(ordered, probability):
    """정렬된 표본의 선형 보간 분위수((n-1)p 위치)를 반환한다."""
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def bootstrap(a, b, seed=0, resamples=2000):
    """이미지 G개를 G번 복원 추출하여 문항 가중 A−B의 percentile 95% CI를 구한다."""
    if type(seed) is not int or type(resamples) is not int or resamples < 1:
        raise ValueError("integer seed and positive resamples required")
    left, right = validate_pair(a, b)
    groups = {}
    for key in sorted(left):
        groups.setdefault(left[key]["cluster"], []).append(left[key]["score"] - right[key]["score"])
    clusters = [(fsum(groups[key]), len(groups[key])) for key in sorted(groups)]
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        selected = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        draws.append(fsum(value for value, _ in selected) / sum(size for _, size in selected))
    draws.sort()
    mean_a = fsum(left[k]["score"] for k in sorted(left)) / len(left)
    mean_b = fsum(right[k]["score"] for k in sorted(right)) / len(right)
    return {"mean_a": mean_a, "mean_b": mean_b,
            "difference": fsum(fsum(groups[k]) for k in sorted(groups)) / len(left),
            "ci95": [percentile(draws, 0.025), percentile(draws, 0.975)],
            "items": len(left), "images": len(clusters),
            "repetitions_a": a["repetitions"], "repetitions_b": b["repetitions"],
            "seed": seed, "resamples": resamples, "direction": "A-B",
            "method": "paired image-cluster percentile bootstrap; item weighted",
            "interpretation": INTERPRETATION}
