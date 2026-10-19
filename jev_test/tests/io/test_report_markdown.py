"""무엇: 보고 문자열 렌더 · 입력: dataclass · 출력: 고정 문구와 미완 행 · 계약 §7-6."""

from jeveval.io.report_markdown import render
from jeveval.types.report import Report, ReportVariant


def test_incomplete_report_has_no_certified_numeric_row():
    report = Report("r", ["m"], [ReportVariant("m", "s", "v", "incomplete", [], [])], [], [], [])
    text = render(report)
    assert "incomplete" in text and "0.01 / 0.02 / 0.05" in text
    assert "감사 v4" in text and "판 5" in text
