"""무엇: 분할 JSON 검증 · 입력: 합성 계획/행 · 출력: 왕복·고정 바이트 · 계약 §6 보정 6."""

from dataclasses import replace

import pytest

from jeveval.data.grouping import group_rows
from jeveval.data.pool import select_pool
from jeveval.data.split import build_split_plan
from jeveval.io.splits import read_split_plan, write_split_plan
from jeveval.types import SourceRow, SplitPlan


def test_literal_bytes_roundtrip_and_no_hangul(tmp_path):
    plan = SplitPlan("s", 1, {"kind": "all"}, {"all": 1}, {"g": ["i"]},
                     {"g": "s:g:i"}, [], ["g"], [], [], {})
    path = tmp_path / "nested" / "s.json"
    write_split_plan(plan, path)
    assert path.read_bytes() == b'''{
 "allocation": {
  "all": 1
 },
 "dev": [],
 "diagnostic_demotions": [],
 "extra": [],
 "groups": {
  "g": [
   "i"
  ]
 },
 "notes": {},
 "pool_rule": {
  "kind": "all"
 },
 "representative": {
  "g": "s:g:i"
 },
 "seed": 1,
 "set": "s",
 "test": [
  "g"
 ]
}
'''
    assert path.read_bytes().isascii()
    assert read_split_plan(path) == plan


def test_input_rows_strata_and_rule_key_order_do_not_change_bytes(tmp_path):
    rows = [SourceRow("klue_mrc_answerable", f"g{i}", {
        "guid": f"g{i}", "source": "wiki" if i % 2 else "news", "context": f"비공개 문맥{i // 2}"})
        for i in range(12)]
    for row in rows:
        row.fields["source"] = "wiki" if int(row.row_id[1:]) // 2 % 2 else "news"
    for index, sequence in enumerate([rows, rows[3:] + rows[:3], list(reversed(rows))]):
        groups = group_rows(sequence, "context")
        cfg = {"pool": dict(reversed(list({"kind": "proportional", "cap": 4,
                                          "stratum_field": "source"}.items()))) if index else
               {"kind": "proportional", "cap": 4, "stratum_field": "source"}}
        strata = {groups.row_to_group[r.row_id]: r.fields["source"] for r in sequence}
        pool = select_pool(groups, cfg["pool"], 20261012, "klue_mrc_answerable", strata)
        plan = build_split_plan(sequence, groups, pool, "klue_mrc_answerable", cfg, 20261012, 0.2)
        write_split_plan(plan, tmp_path / f"{index}.json")
    assert (tmp_path / "0.json").read_bytes() == (tmp_path / "1.json").read_bytes() == (tmp_path / "2.json").read_bytes()
    assert (tmp_path / "0.json").read_bytes().isascii()


def test_actual_korean_demotion_roundtrip_and_other_hangul_rejected(tmp_path):
    rows = [SourceRow("kote_escalation", "0", {"text": "원문 표식", "labels": [1],
                                             "labels_majority": ["없음"]})]
    groups = group_rows(rows, "text")
    cfg = {"pool": {"kind": "all"}, "demotion": {"emotions": ["화남/분노", "없음"], "min_positive": 1}}
    pool = select_pool(groups, cfg["pool"], 1, "kote_escalation")
    plan = build_split_plan(rows, groups, pool, "kote_escalation", cfg, 1, 0.2,
                            label_names=["화남/분노", "없음"])
    path = tmp_path / "kote.json"
    write_split_plan(plan, path)
    assert read_split_plan(path).diagnostic_demotions == ["화남/분노"]
    assert "원문 표식" not in path.read_text()
    with pytest.raises(ValueError, match="Hangul"):
        write_split_plan(replace(plan, notes={"leak": "원문 표식"}), path)
