"""무엇: 라벨 없는 대화 경계 · 입력: 투영 발화 · 출력: frozen prefix · 계약 §8-7 판 5 보정 2 WP3."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DialoguePrefix:
    dialogue_id: str
    turn_index: int
    dialogue: tuple[tuple[str, str], ...]

    @property
    def logical_id(self):
        return f"kosgd2_pilot:{self.dialogue_id}:{self.turn_index}"
