"""무엇: KorFin 항목 검사 · 입력: 합성 SID 행 · 출력: 원본 순서·정답·flag · 계약 §6-2."""

from copy import deepcopy

import pytest

from jeveval.data.items.common import summarize
from jeveval.data.items.korfin import _bindings, build_items
from jeveval.types import SourceRow


def _row(sid, aspect, sentiment, text="a"):
    return SourceRow("korfin_asc", sid, dict(SID=sid, SRC=text, ASPECT=aspect, SENTIMENT=sentiment))


def test_source_order_gold_flags_and_summary_count_items(settings, plan_for, label_rules):
    task, lists = settings("korfin_asc")
    rows = [_row("20_2", "missing1", "NEGATIVE"), _row("20_0", "a", "POSITIVE"),
            _row("20_1", "missing2", "NEUTRAL"), _row("30_0", "b", "NEUTRAL", "b")]
    before = deepcopy((rows, lists))
    result = build_items(rows, plan_for(rows, task), task, lists, label_rules)
    item = result["dev"][0]
    assert (item.group_id, item.item_id, item.state_fields) == ("20", "20", "a")
    assert [q.id for q in item.questions] == ["aspect_1", "aspect_2", "aspect_3"]
    assert [q.gold for q in item.questions] == ["NEGATIVE", "POSITIVE", "NEUTRAL"]
    assert "missing1" in item.questions[0].instructions
    assert item.meta["flags"] == ["aspect_not_in_text:aspect_1", "aspect_not_in_text:aspect_3"]
    assert summarize(result)["dev"]["flags"] == {"aspect_not_in_text": 1}
    assert (rows, lists) == before and result["extra"] == []
    assert result["test"][0].item_id == "30"


def test_duplicate_aspect_and_mixed_src_stop(settings, plan_for, label_rules):
    task, lists = settings("korfin_asc")
    rows = [_row("20_0", "a", "POSITIVE"), _row("20_1", "a", "NEGATIVE")]
    with pytest.raises(ValueError, match="ASPECT"):
        build_items(rows, plan_for(rows, task), task, lists, label_rules)
    with pytest.raises(ValueError, match="SRC"):
        _bindings([rows[0], _row("30_0", "b", "NEUTRAL", "b")])
