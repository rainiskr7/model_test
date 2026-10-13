"""무엇: 출현 클래스 macro-F1 · 입력: 정답·예측 목록 · 출력: F1Result · 계약 §7-1."""

from collections import Counter
import math

from jeveval.types import F1Result


def macro_f1(gold: list[str], predicted: list[str]) -> F1Result:
    """정답 또는 예측에 출현한 클래스만 포함하고 분모 0 비율은 그대로 보존한다."""
    if len(gold) != len(predicted):
        raise ValueError("gold and predicted lengths differ")
    support, counts = Counter(gold), Counter(predicted)
    true_positives = Counter(g for g, p in zip(gold, predicted) if g == p)
    classes = sorted(support.keys() | counts.keys())
    stats, scores = {}, {}
    for cls in classes:
        tp = true_positives[cls]
        stats[cls] = dict(support=support[cls], predicted=counts[cls], tp=tp,
                          recall=dict(num=tp, den=support[cls]), precision=dict(num=tp, den=counts[cls]))
        scores[cls] = 2 * tp / (support[cls] + counts[cls])
    mean = math.fsum(scores.values()) / len(classes) if classes else None
    return F1Result(classes, scores, mean, stats)
