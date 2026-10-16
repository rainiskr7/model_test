"""채점 결과 자료형의 JSON·중첩 타입·frozen 경계."""

import pytest

from jeveval.types.scoring import AnswerParse, CalibResult, F1Result, Observation, SlotJudgement
from tests.types.record_support import check_record
from tests.types.samples import function_results


@pytest.mark.parametrize("record", [r for r in function_results()
    if isinstance(r, (AnswerParse, CalibResult, F1Result, SlotJudgement))]
    + [Observation("s:g:i", "g", "q", "true", "false")], ids=lambda r: type(r).__name__)
def test_scoring_record_boundaries(record):
    check_record(record)
