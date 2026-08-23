from __future__ import annotations

import pytest

from shared.multimodal.publish.classify import classify_record
from shared.multimodal.publish.schema import RecordClass


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ({"response": "정상 답변"}, RecordClass.MEASURED),
        ({"response": "{'error': 설명}"}, RecordClass.MEASURED),
        ({"response": ""}, RecordClass.MEASURED),
        ({"response": {"error": "timeout"}}, RecordClass.ERRORED),
        ({"response": {"value": "not an error"}}, RecordClass.UNRESOLVED),
        ({"response": None}, RecordClass.UNRESOLVED),
        ({}, RecordClass.UNRESOLVED),
        ({"error": "request failed", "response": "A"}, RecordClass.ERRORED),
        ({"error": "", "response": "A"}, RecordClass.MEASURED),
    ],
)
def test_type_based_classification(record, expected):
    assert classify_record(record) is expected


def test_alternate_response_field():
    assert classify_record({"prediction": "ok"}, "prediction") is RecordClass.MEASURED
