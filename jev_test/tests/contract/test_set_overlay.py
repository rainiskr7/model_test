"""무엇: overlay 공격 입력 · 입력: 합성 설정/task · 출력: 닫힌 스키마 거부 · 계약 판 5 보정 1 §9."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from jeveval.contract.set_overlay import task_names, validate_overlay


def valid():
    return dict(schema="set_overlay/1", id="alias", tasks=["alias.yaml"],
                dataset=dict(id="alias", family="kosgd", map=dict(primary_variant="full")),
                split_rules=dict(family="kosgd"))


def check(value, stem="alias", tasks=None):
    return validate_overlay(value, stem, {"kosgd"}, {"kosgd"},
                            tasks if tasks is not None else {"alias.yaml": SimpleNamespace(set="alias", variant="full")})


def test_valid_overlay_is_not_mutated():
    value = valid()
    before = deepcopy(value)
    assert check(value) == [] and value == before


@pytest.mark.parametrize("attack", ["schema", "stem", "base", "id", "nested", "family", "representative",
                                    "seed", "fraction", "lists", "primary", "task_set", "missing_task",
                                    "empty_tasks", "traversal", "duplicate", "cycle"])
def test_overlay_rejects_boundary_attacks(attack):
    value, stem, tasks = valid(), "alias", None
    if attack == "schema": value["schema"] = "other/1"
    if attack == "stem": stem = "other"
    if attack == "base": value["id"] = stem = "kosgd"
    if attack == "id": value["dataset"]["id"] = "other"
    if attack == "nested": value["dataset"]["map"]["x"] = [{"id": "kosgd"}]
    if attack == "family": value["split_rules"]["family"] = "kmhas"
    if attack == "representative": value["dataset"]["family"] = value["split_rules"]["family"] = "unknown"
    if attack == "seed": value["split_rules"]["seed"] = 1
    if attack == "fraction": value["split_rules"]["dev_fraction"] = .5
    if attack == "lists": value["lists"] = {}
    if attack == "primary": value["dataset"]["map"].clear()
    if attack == "task_set": tasks = {"alias.yaml": SimpleNamespace(set="kosgd", variant="full")}
    if attack == "missing_task": tasks = {}
    if attack == "empty_tasks": value["tasks"] = []
    if attack == "traversal": value["tasks"] = ["../alias.yaml"]
    if attack == "duplicate": value["tasks"] *= 2
    if attack == "cycle": value["dataset"]["loop"] = value["dataset"]
    assert check(value, stem, tasks)


def test_task_names_rejects_types_and_reserved_file():
    for value in (None, {}, {"tasks": [None]}, {"tasks": ["b1.yaml"]}, {"tasks": "a.yaml"}):
        assert task_names(value) == []
