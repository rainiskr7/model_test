"""무엇: 대표·분할 검증 · 입력: fixture·합성 행 · 출력: 계획·강등·충돌 검증 · 계약 §6."""

import json
from pathlib import Path
import random

from jeveval.data.grouping import group_rows
from jeveval.data.pool import select_pool
from jeveval.data.split import _demotions, _shuffled_groups, build_split_plan, check_split_plan
from jeveval.types import Groups, PoolResult, SourceRow


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "splits"


def test_deterministic_fixture_intermediate_and_final_orders():
    f = json.loads((FIXTURES / "deterministic.json").read_text())
    groups = Groups({}, f["groups"])
    cfg = {"pool": {"kind": "simple_cap", "cap": f["cap"]}}
    pool = select_pool(groups, cfg["pool"], f["seed"], f["set"])
    shuffled = _shuffled_groups(pool.group_ids, f["seed"], f["set"])
    boundary = len(shuffled) // 5
    assert shuffled[:boundary] == f["expected"]["dev"]
    assert shuffled[boundary:] == f["expected"]["test"]
    plan = build_split_plan([], groups, pool, f["set"], cfg, f["seed"], 0.2)
    assert plan.representative == f["expected"]["representative"]
    assert plan.dev == sorted(f["expected"]["dev"])
    assert plan.test == sorted(f["expected"]["test"])
    assert list(plan.groups) == sorted(pool.group_ids)
    assert all(v == sorted(v) for v in plan.groups.values())
    assert plan.pool_rule == cfg["pool"]


def test_label_conflicts_fixture_and_pool_scope():
    f = json.loads((FIXTURES / "label_conflicts.json").read_text())
    rows = [SourceRow("kmhas", r["row_id"], r) for r in f["rows"]]
    groups = group_rows(rows, "text")
    cfg = {"pool": {"kind": "all"}, "label_field": "gold"}
    pool = select_pool(groups, cfg["pool"], 1, "kmhas")
    plan = build_split_plan(rows, groups, pool, "kmhas", cfg, 1, 0.2)
    assert {k: plan.notes[k] for k in f["expected"]["notes"]} == f["expected"]["notes"]
    plan = build_split_plan(rows, groups, PoolResult(["9"], {"all": 1}), "kmhas", cfg, 1, 0.2)
    assert plan.notes["label_conflict_groups_total"] == 1
    assert plan.notes["label_conflict_groups_pool"] == 0
    assert plan.groups == {"9": ["9"]}


def test_label_order_and_duplicates_do_not_create_conflict():
    rows = [SourceRow("kmhas", str(i), {"text": "same", "label": labels})
            for i, labels in enumerate([[1, 2], [2, 1, 1]])]
    groups = group_rows(rows, "text")
    cfg = {"pool": {"kind": "all"}, "label_field": "label"}
    plan = build_split_plan(rows, groups, select_pool(groups, cfg["pool"], 1, "kmhas"), "kmhas", cfg, 1, 0.2)
    assert plan.notes["label_conflict_groups_total"] == 0


def test_demotion_fixture():
    f = json.loads((FIXTURES / "diagnostic_demotions.json").read_text())
    assert _demotions(f["positive_counts"], 50) == f["expected"]["diagnostic_demotions"]


def test_kote_counts_only_pool_representatives_with_korean_demotion():
    seed, name = 20261012, "kote_escalation"
    rep = random.Random(f"{seed}:{name}:rep:0").choice(["0", "1"])
    rows = [SourceRow(name, str(i), {"text": "same", "labels": [0, 1],
            "votes": {"화남/분노": 1, "없음": 3} if str(i) == rep else {"화남/분노": 3},
            "labels_majority": ["없음"] if str(i) == rep else ["화남/분노"]})
            for i in range(2)]
    rows.append(SourceRow(name, "2", {"text": "outside pool", "labels": [0],
                                    "labels_majority": ["화남/분노"]}))
    groups = group_rows(rows, "text")
    cfg = {"pool": {"kind": "simple_cap", "cap": 1}, "label_field": "labels_majority",
           "demotion": {"emotions": ["화남/분노", "없음"], "min_positive": 1}}
    plan = build_split_plan(rows, groups, PoolResult(["0"], {"all": 1}), name, cfg, seed, 0.2,
                            label_names=["화남/분노", "없음"])
    assert plan.diagnostic_demotions == ["화남/분노"]
    assert plan.notes["label_conflict_groups_pool"] == 1


def test_kote_conflicts_follow_label_field_only():
    name = "kote_escalation"
    rows = [SourceRow(name, str(i), {"text": "same", "labels": [i],
                                    "labels_majority": ["없음"]}) for i in range(2)]
    groups = group_rows(rows, "text")
    cfg = {"pool": {"kind": "all"}, "label_field": "labels_majority"}
    pool = select_pool(groups, cfg["pool"], 1, name)
    plan = build_split_plan(rows, groups, pool, name, cfg, 1, 0.2)
    assert plan.notes["label_conflict_groups_total"] == 0
    cfg["label_field"] = "labels"
    plan = build_split_plan(rows, groups, pool, name, cfg, 1, 0.2)
    assert plan.notes["label_conflict_groups_total"] == 1


def test_kosgd_fixed_representative_and_korfin_row_count():
    rows = [SourceRow("kosgd", f"d#{i}", {"dialogue_id": "d", "turn_index": i}) for i in [0, 2]]
    groups = group_rows(rows, "dialogue_id")
    fixed = [{"dialogue_id": "d", "turn_index": 2}]
    cfg = {"pool": {"kind": "fixed_selection", "path": "audit.json", "field": "selected_turns"}}
    pool = select_pool(groups, cfg["pool"], 1, "kosgd", fixed=fixed)
    plan = build_split_plan(rows, groups, pool, "kosgd", cfg, 1, 0.2, fixed=fixed)
    assert plan.representative == {"d": "kosgd:d:2"}
    assert plan.groups == {"d": ["0", "2"]}
    rows = [SourceRow("korfin_asc", sid, {"SID": sid, "SRC": "문장"}) for sid in ["42_1", "42_0"]]
    groups = group_rows(rows, "SRC")
    cfg = {"pool": {"kind": "all"}}
    pool = select_pool(groups, cfg["pool"], 1, "korfin_asc")
    plan = build_split_plan(rows, groups, pool, "korfin_asc", cfg, 1, 0.2)
    assert plan.groups == {"42": ["42"]}
    assert plan.representative == {"42": "korfin_asc:42:42"}
    assert plan.notes["n_rows"] == 2


def test_functionchat_extra_covers_every_nonrepresentative():
    f = json.loads((FIXTURES / "union_find.json").read_text())
    name = "fc_call_decision"
    rows = [SourceRow(name, str(r["serial_num"]), r) for r in f["rows"]]
    groups = group_rows(rows, "fc_components")
    cfg = {"pool": {"kind": "all"}, "extra": True}
    pool = select_pool(groups, cfg["pool"], 1, name)
    plan = build_split_plan(rows, groups, pool, name, cfg, 1, 0.5)
    all_ids = {f"{name}:{g}:{i}" for g, items in groups.members.items() for i in items}
    assert set(plan.extra).isdisjoint(plan.representative.values())
    assert set(plan.extra) | set(plan.representative.values()) == all_ids
    assert plan.extra == sorted(plan.extra)
    assert len(plan.dev) == 1 and len(plan.test) == 2


def test_plan_semantics_extra_membership_without_set_inference():
    from dataclasses import replace
    from jeveval.types import SplitPlan

    plan = SplitPlan("synthetic", 1, {}, {}, {"g": ["1", "2", "3"]},
                     {"g": "synthetic:g:1"}, ["g"], [], [], [], {})
    assert check_split_plan(plan) == []
    assert check_split_plan(replace(plan, extra=["synthetic:g:2"])) == []
    for edits in [dict(dev=[]), dict(test=["g"]), dict(dev=["g", "g"]),
                  dict(representative={}), dict(representative={"g": "other:g:1"}),
                  dict(representative={"g": "synthetic:h:1"}),
                  dict(extra=["synthetic:g:1"]), dict(extra=["synthetic:g:9"]),
                  dict(extra=["synthetic:g:3", "synthetic:g:2"]),
                  dict(extra=["synthetic:g:2", "synthetic:g:2"])]:
        assert check_split_plan(replace(plan, **edits)), edits
