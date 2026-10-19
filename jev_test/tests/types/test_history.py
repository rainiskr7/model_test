"""무엇: 역사 경계 불변성 · 입력: StageCheck · 출력: frozen · 계약 §8-1."""

from dataclasses import FrozenInstanceError
import pytest
from jeveval.types.history import StageCheck


def test_history_stage_check_frozen():
    value = StageCheck("dev", "incomplete", None, 0, None, {})
    with pytest.raises(FrozenInstanceError):
        value.status = "verified_complete"
