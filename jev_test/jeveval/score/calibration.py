"""무엇: ECE·Brier·log loss · 입력: 파싱 답·정답 · 출력: CalibResult · 계약 §7-1."""

import math

from jeveval.types import CalibResult, ParsedAnswer


def _bins(parsed, gold):
    bins = []
    for index in range(15):
        lo, hi = index / 15, (index + 1) / 15
        members = [(p, g) for p, g in zip(parsed, gold) if lo <= p.probs[p.answer]
                   and (p.probs[p.answer] < hi or index == 14 and p.probs[p.answer] == 1)]
        n = len(members)
        acc = sum(p.answer == g for p, g in members) / n if n else None
        conf = math.fsum(p.probs[p.answer] for p, _ in members) / n if n else None
        bins.append(dict(index=index, lo=lo, hi=hi, n=n, acc=acc, conf=conf))
    return bins


def calibrate(parsed: list[ParsedAnswer], gold: list[str]) -> CalibResult:
    """보정 축은 선택한 답의 확률; 수락 점수는 ParsedAnswer.confidence (score/tasks)."""
    if len(parsed) != len(gold):
        raise ValueError("parsed and gold lengths differ")
    if any(g not in p.probs for p, g in zip(parsed, gold)):
        raise ValueError("gold missing from probabilities")
    bins = _bins(parsed, gold)
    if not parsed:
        return CalibResult(None, bins, None, None)
    n = len(parsed)
    ece = math.fsum(b["n"] * abs(b["acc"] - b["conf"]) for b in bins if b["n"]) / n
    brier = math.fsum((prob - (cls == g)) ** 2 for p, g in zip(parsed, gold)
                      for cls, prob in p.probs.items()) / n
    loss = math.fsum(-math.log(min(1, max(1e-12, p.probs[g]))) for p, g in zip(parsed, gold)) / n
    return CalibResult(ece, bins, brier, loss)
