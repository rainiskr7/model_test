"""무엇: 보고 경계 불변성 · 입력: Report · 출력: frozen · 계약 §8-1."""

from dataclasses import FrozenInstanceError
import pytest
from jeveval.types.report import Report


def test_report_is_frozen():
    value = Report("r", [], [], [], [], [])
    with pytest.raises(FrozenInstanceError):
        value.run_id = "changed"
