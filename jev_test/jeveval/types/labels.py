"""무엇: 라벨 어휘 자료형 · 입력: configs/datasets.yaml 의 label_vocab · 출력: LabelVocab · 계약 §6-2·§8-1."""

from dataclasses import dataclass

from .base import JsonRecord


@dataclass(frozen=True)
class LabelVocab(JsonRecord):
    """정답 규칙 등록표(score/labels.rules)를 만드는 동결 어휘. 선택한 질문 목록(task yaml)과는 다른 목록이다."""

    kosgd_acts: list[str]
    kmhas: list[str]
    kote: list[str]
