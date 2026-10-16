"""T0 단계 전달 객체: JSON 기록과 메모리 핸들의 서로 다른 경계."""

import pytest

from jeveval.types.t0 import T0Boundary
from jeveval.types.t0_io import T0Input, T0Inputs, T0Policy, T0Reference, T0Sources
from tests.types.record_support import check_memory_record, check_record


@pytest.mark.parametrize("record", [
    T0Input("c", {"state": "s"}, {"state": "s"}, "r" * 64, "e" * 64, "f" * 64,
            [100], T0Boundary([100], 100, "reject")),
    T0Policy(2, .02, {"clef": ["batch_1"], "pplx_v1_1": ["single"]}, "a" * 64)],
    ids=lambda r: type(r).__name__)
def test_t0_io_json_record_boundaries(record):
    check_record(record)


@pytest.mark.parametrize("record", [T0Inputs({"schema": "t0_inputs/1"}, [], "a" * 64),
    T0Reference("clef", object(), object()), T0Sources({}, {}, {}, 42)], ids=lambda r: type(r).__name__)
def test_t0_io_memory_record_boundaries(record):
    check_memory_record(record)


def test_t0_input_restores_nested_boundary():
    value = T0Input("c", {}, {}, "r", "e", "f", [100], T0Boundary([100], 100, "reject"))
    source = value.to_dict()
    restored = T0Input.from_dict(source)
    assert isinstance(restored.boundary, T0Boundary)
    source["boundary"]["lengths"].clear()
    assert restored.boundary.lengths == [100]
