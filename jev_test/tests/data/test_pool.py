"""무엇: 평가 풀 검증 · 입력: 기존 fixture·경계 모집단 · 출력: 할당/선정 검증 · 계약 §6."""

import json
from pathlib import Path

import pytest

from jeveval.data.pool import select_pool
from jeveval.types import Groups


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "splits"


def test_proportional_fixture_and_tie():
    f = json.loads((FIXTURES / "proportional.json").read_text())
    strata = {g: h for h, ids in f["strata"].items() for g in ids}
    groups = Groups({}, {g: [g] for g in strata})
    pool = select_pool(groups, {"kind": "proportional", "cap": f["cap"]}, f["seed"], f["set"], strata)
    assert pool.allocation == f["expected"]["allocation"]
    assert {h: [g for g in pool.group_ids if strata[g] == h] for h in f["strata"]} == f["expected"]["selected_by_stratum"]
    tie = f["tie_case"]
    groups = Groups({}, {h: [h] for h in reversed(tie["stratum_counts"])})
    pool = select_pool(groups, {"kind": "proportional", "cap": tie["cap"]}, f["seed"], f["set"],
                       {h: h for h in groups.members})
    assert pool.allocation == tie["expected_allocation"]


def test_simple_cap_fixture_and_all():
    f = json.loads((FIXTURES / "deterministic.json").read_text())
    groups = Groups({}, f["groups"])
    pool = select_pool(groups, {"kind": "simple_cap", "cap": f["cap"]}, f["seed"], f["set"])
    assert pool.group_ids == f["expected"]["pool"]
    assert pool.allocation == {"all": 7}
    assert select_pool(groups, {"kind": "all"}, 1, "s").group_ids == sorted(f["groups"])


@pytest.mark.parametrize("kind", ["simple_cap", "proportional"])
@pytest.mark.parametrize("cap", [2, 3])
def test_cap_at_or_above_population(kind, cap):
    groups = Groups({}, {"b": ["b"], "a": ["a"]})
    pool = select_pool(groups, {"kind": kind, "cap": cap}, 1, "s", {"a": "x", "b": "y"})
    assert pool.group_ids == ["a", "b"]
    assert pool.allocation == ({"x": 1, "y": 1} if kind == "proportional" else {"all": 2})


@pytest.mark.parametrize("kind", ["simple_cap", "proportional"])
@pytest.mark.parametrize("cap", [0, -1, True, 1.5, "2", None])
def test_invalid_caps(kind, cap):
    with pytest.raises(ValueError, match="positive integer"):
        select_pool(Groups({}, {"a": ["a"]}), {"kind": kind, "cap": cap}, 1, "s", {"a": "x"})


@pytest.mark.parametrize("kind", ["all", "simple_cap", "proportional", "fixed_selection"])
def test_empty_population(kind):
    with pytest.raises(ValueError, match="empty population"):
        select_pool(Groups({}, {}), {"kind": kind, "cap": 1}, 1, "s")


def test_fixed_selection():
    groups = Groups({}, {"d1": ["0", "2"], "d2": ["0"], "unused": ["0"]})
    fixed = [{"dialogue_id": "d2", "turn_index": 0}, {"dialogue_id": "d1", "turn_index": 2}]
    pool = select_pool(groups, {"kind": "fixed_selection"}, 1, "kosgd", fixed=fixed)
    assert pool.group_ids == ["d1", "d2"]
    assert pool.allocation == {"all": 2}


@pytest.mark.parametrize("fixed", [
    [], [{"dialogue_id": "missing", "turn_index": 0}],
    [{"dialogue_id": "d", "turn_index": i} for i in [0, 2]],
    [{"dialogue_id": "d", "turn_index": 1}],
    [{"dialogue_id": "d", "turn_index": 100}],
    [{"dialogue_id": "d", "turn_index": -1}],
    [{"dialogue_id": "d", "turn_index": True}],
])
def test_invalid_fixed_selection(fixed):
    with pytest.raises(ValueError):
        select_pool(Groups({}, {"d": ["0", "2"]}), {"kind": "fixed_selection"}, 1, "kosgd", fixed=fixed)


def test_missing_stratum_rejected():
    with pytest.raises(ValueError, match="cover every group"):
        select_pool(Groups({}, {"a": ["a"]}), {"kind": "proportional", "cap": 1}, 1, "s", {})


def test_fixed_selection_rejects_other_turn_of_excluded_dialogue():
    groups = Groups({}, {"old": ["0", "2"], "new": ["0"]})
    cfg = {"kind": "fixed_selection", "exclude": [{"path": "old", "field": "selected_turns", "by": "dialogue_id"}]}
    with pytest.raises(ValueError, match="exclusion evidence"):
        select_pool(groups, cfg, 1, "kosgd2", fixed=[{"dialogue_id": "new", "turn_index": 0}])
    with pytest.raises(ValueError, match="intersects"):
        select_pool(groups, cfg, 1, "kosgd2", fixed=[{"dialogue_id": "old", "turn_index": 2}], excluded={"old"})
