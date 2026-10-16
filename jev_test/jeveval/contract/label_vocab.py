"""무엇: 라벨 어휘 검사 · 입력: 셋 id → label_vocab 목록 · 출력: LabelVocab 또는 오류 목록 · 계약 §6-2·§8-1."""

from jeveval.types import LabelVocab

SETS = {"kosgd": "kosgd_acts", "kmhas": "kmhas", "kote_escalation": "kote"}
CLOSE_ACTS = ("GOODBYE", "THANK_YOU")


def _names(value, set_id):
    if (not isinstance(value, list) or not value or any(type(n) is not str or not n for n in value)
            or len(set(value)) != len(value)):
        return f"{set_id}: label_vocab must be a non-empty list of unique names"
    return None


def validate_label_vocab(entries: dict) -> LabelVocab | list[str]:
    """세 셋의 어휘가 모두 있고 고유한 이름 목록이며, KoSGD 는 CLOSE 를 이루는 두 act 를 포함해야 한다."""
    if not isinstance(entries, dict) or set(entries) != set(SETS):
        return [f"label_vocab required for exactly: {', '.join(sorted(SETS))}"]
    errors = [e for set_id in SETS for e in [_names(entries[set_id], set_id)] if e]
    if not errors and not set(CLOSE_ACTS) <= set(entries["kosgd"]):
        errors.append("kosgd: label_vocab must include GOODBYE and THANK_YOU (CLOSE)")
    return errors or LabelVocab(**{field: list(entries[set_id]) for set_id, field in SETS.items()})
