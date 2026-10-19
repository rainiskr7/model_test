"""무엇: 설정 자료형 경계 · 입력: 검증 설정 · 출력: frozen SetEntry · 계약 판 5 보정 1 §8-1."""

from dataclasses import FrozenInstanceError

import pytest

from jeveval.types.set_config import SetEntry


def test_entry_fields_are_frozen():
    entry = SetEntry("s", "s", {"id": "s"}, {}, None, ("configs/tasks/s.yaml",))
    with pytest.raises(FrozenInstanceError):
        entry.set_id = "changed"
    assert entry.overlay_path is None and entry.task_files == ("configs/tasks/s.yaml",)
