"""무엇: KoSGD 고정 칸·묶음 판정 · 입력: 의도·카탈로그·예측 · 출력: 칸/SlotJudgement · 계약 §7-2."""

from collections import Counter

from jeveval.types import SlotJudgement


def fixed_gold(gold_intents: list[str], catalog_order: list[str]) -> list[str]:
    """NONE을 먼저 제외하고 카탈로그 순서로 두 정답 칸을 만든다."""
    if len(set(catalog_order)) != len(catalog_order):
        raise ValueError("duplicate catalog entries")
    intents = [intent for intent in gold_intents if intent != "NONE"]
    if len(intents) > 2 or len(set(intents)) != len(intents):
        raise ValueError("gold requires at most two distinct intents")
    order = {intent: index for index, intent in enumerate(catalog_order)}
    if any(intent not in order for intent in intents):
        raise ValueError("gold intent outside catalog")
    return sorted(intents, key=order.get) + ["NONE"] * (2 - len(intents))


def judge_slots(predicted: list[str], gold_intents: list[str],
                 catalog_order: list[str]) -> SlotJudgement:
    """묶음 정답은 순서 무관, 칸별 정답은 예측과 무관하게 고정한다."""
    if len(predicted) != 2:
        raise ValueError("predicted must have two slots")
    fixed = fixed_gold(gold_intents, catalog_order)
    duplicate = predicted[0] == predicted[1] and predicted[0] != "NONE"
    correct = Counter(predicted) == Counter(fixed) and not duplicate
    return SlotJudgement(fixed, correct, duplicate, correct and predicted != fixed)
