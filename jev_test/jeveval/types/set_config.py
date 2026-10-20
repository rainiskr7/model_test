"""무엇: 셋별 설정 경계 · 입력: 검증된 공용/overlay 설정 · 출력: SetEntry · 계약 판 5 보정 1 §8-1."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SetEntry:
    set_id: str
    family: str
    dataset: dict
    split_rules: dict
    overlay_path: str | None
    task_files: tuple[str, ...]
    analysis: dict[str, str] | None = None
