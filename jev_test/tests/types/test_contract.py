"""계약 경계 자료형의 왕복·frozen·필수 필드."""

import pytest

from jeveval.types.contract import B1Call, B1Config, B1Response, Validated
from tests.types.record_support import check_record
from tests.types.samples import function_results


@pytest.mark.parametrize("record", [r for r in function_results() if isinstance(r, (B1Call, B1Config, Validated))]
    + [B1Response(None, [], [{"token": "A", "logprob": float("-inf")}], {"input_tokens": 1})],
    ids=lambda r: type(r).__name__)
def test_contract_record_boundaries(record):
    check_record(record)
