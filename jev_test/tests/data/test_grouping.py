"""무엇: 묶음 규칙 검증 · 입력: 합성 행·기존 fixture · 출력: Groups 검증 · 계약 §6."""

import json
from pathlib import Path

import pytest

from jeveval.data.grouping import group_rows
from jeveval.types import SourceRow


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "splits"


def test_union_find_fixture_and_order_invariance():
    fixture = json.loads((FIXTURES / "union_find.json").read_text())
    rows = [SourceRow("fc_call_decision", str(r["serial_num"]), r) for r in fixture["rows"]]
    result = group_rows(rows, "fc_components")
    assert result.members == fixture["expected"]["groups"]
    assert result == group_rows(list(reversed(rows)), "fc_components")
    assert result.row_to_group == {"11": "11", "12": "11", "13": "11", "14": "14", "15": "15"}


def test_label_conflict_fixture_grouping():
    fixture = json.loads((FIXTURES / "label_conflicts.json").read_text())
    rows = [SourceRow("kmhas", r["row_id"], r) for r in fixture["rows"]]
    assert group_rows(rows, "text").members == fixture["expected"]["groups"]


def test_numeric_minimum_exact_text_and_string_sort():
    rows = [SourceRow("kmhas", i, {"text": text})
            for i, text in [("10", "가"), ("2", "가"), ("3", "가 "), ("4", "가")]]
    assert group_rows(rows, "text").members == {"2": ["10", "2"], "3": ["3"], "4": ["4"]}


def test_kosgd_row_and_item_identifiers():
    rows = [SourceRow("kosgd", f"{d}#{i}", {"dialogue_id": d, "turn_index": i})
            for d, i in [("d1", 10), ("d1", 2), ("d2", 2)]]
    groups = group_rows(rows, "dialogue_id")
    assert groups.members == {"d1": ["10", "2"], "d2": ["2"]}
    assert groups.row_to_group["d2#2"] == "d2"


def test_klue_min_guid_and_source_consistency():
    rows = [SourceRow("klue_mrc_answerable", g, {"guid": g, "context": "문맥", "source": s})
            for g, s in [("g2", "wiki"), ("g10", "wiki")]]
    assert group_rows(rows, "context").members == {"g10": ["g10", "g2"]}
    rows[1].fields["source"] = "news"
    with pytest.raises(ValueError, match="inconsistent source"):
        group_rows(rows, "context")


@pytest.mark.parametrize("rows,rule,match", [
    ([SourceRow("s", "a:b", {"text": "x"})], "text", "IDs"),
    ([SourceRow("s", "1", {"text": "x"})] * 2, "text", "duplicate"),
    ([SourceRow("kosgd", "d#0", {"dialogue_id": "d:x", "turn_index": 0})], "dialogue_id", "IDs"),
    ([SourceRow("s", "1", {"input_messages": [], "input_tools": []})], "fc_components", "user"),
    ([SourceRow("s", "1", {"text": "x"})], "unknown", "unknown"),
    ([SourceRow("s", "1_0", {"SID": "1_0", "SRC": "a"}),
      SourceRow("s", "1_1", {"SID": "1_1", "SRC": "b"})], "SRC", "collision"),
])
def test_invalid_groups(rows, rule, match):
    with pytest.raises(ValueError, match=match):
        group_rows(rows, rule)
