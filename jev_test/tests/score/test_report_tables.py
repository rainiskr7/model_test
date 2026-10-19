"""무엇: 공개 투영과 공통 오류 · 입력: 통계 dataclass · 출력: 교집합 분모 · 계약 §7-6."""

from dataclasses import replace

import pytest

from jeveval.score.report_tables import common_errors, safe_id
from jeveval.types.report import KosgdDecomposition, ReportVariant


def test_common_error_counts_only_valid_intersection():
    d = KosgdDecomposition("dev", 0, 0, 0, 0, {}, [], 0, ["a", "b"], ["b"])
    a = ReportVariant("m1", "s", "full", "incomplete", [], [], decompositions=[d])
    b = replace(a, model="m2", decompositions=[replace(d, valid_ids=["b", "c"], wrong_ids=["b", "c"])])
    c = common_errors([a, b])[0]
    assert (c.common, c.excluded_left, c.excluded_right, c.both_wrong) == (1, 1, 1, 1)


def test_arbitrary_path_is_not_public_identifier():
    with pytest.raises(ValueError):
        safe_id("private/path")
