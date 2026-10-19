"""무엇: 조립 리팩터 바이트 보존 · 입력: d41e8b9 합성 기준 · 출력: Item/요청 동치 · 계약 §6-2·§9."""

from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest

from jeveval.data.items.common import fields
from jeveval.types import Item, ItemFields
from tests.data.items.byte_support import BUILDERS, sample, wire_snapshot
from tests.types.samples import bound


@pytest.mark.parametrize("name", list(BUILDERS))
def test_item_and_systemone_b1_bytes_match_before_refactor(name):
    """기준값은 ItemFields 도입 전 실제 builder/planner 출력이며 실행 중 갱신하지 않는다."""
    expected = json.loads(Path(__file__).with_name("item_wire_d41e8b9.json").read_text())
    assert wire_snapshot(name) == expected[name]
    _, stages = sample(name)
    for items in stages.values():
        for item in items:
            assert Item.from_dict(item.to_dict()) == item


def test_item_fields_frozen_and_deeply_detached():
    """frozen과 별개로 state·질문·meta·baseline의 모든 가변 입력 별칭을 끊는다."""
    state, questions, service, baseline = {"nested": ["원문"]}, [bound()], ["s"], {"copy_prev": ["NONE"]}
    result = fields(state, questions, service=service, baseline=baseline, flags=["z", "a", "z"])
    assert isinstance(result, ItemFields) and result.meta["flags"] == ["a", "z"]
    with pytest.raises(FrozenInstanceError):
        result.baseline = None
    state["nested"].clear()
    questions[0].criteria.clear()
    service.clear()
    baseline["copy_prev"].clear()
    assert result.state_fields == {"nested": ["원문"]}
    assert result.questions[0].criteria and result.meta["service"] == ["s"]
    assert result.baseline == {"copy_prev": ["NONE"]}
