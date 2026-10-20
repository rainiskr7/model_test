"""무엇: D1 선정→분할→T0 통합 · 입력: 합성 대화·fixture · 출력: 예약 대화 풀 밖 · 계약 판 5 보정 1 §6-2."""

import json

from audits.kosgd2_selection.select_turns import run, select
from jeveval.data.t0_fixture import resolve_source
from jeveval.io.config import read_yaml
from jeveval.io.set_config import entry
from jeveval.io.splits import write_split_plan
from jeveval.io.t0_sources import read_sources
from jeveval.run.make_splits import _make_plan
from tests.run.cli_support import Harness
from tests.run.file_support import put_yaml


def prepare(root):
    Harness(root, "kosgd2", "full")
    rows = [dict(dialogue_id=f"d{i}", services=[], turns=[dict(speaker="USER", utterance="synthetic", frames=[])
            for _ in range(3)]) for i in range(5)]
    for name in ("kosgd", "kosgd2"):
        directory = root / "dataset" / name
        directory.mkdir(exist_ok=True)
        (directory / "dialogues_1.json").write_text(json.dumps(rows))
    (root / "old.json").write_text(json.dumps(dict(selected_turns=[dict(dialogue_id="d0", turn_index=0)])))
    fixture = dict(schema="t0_fixture/1", cases=[dict(state_ref=dict(set="kosgd", row_id="d2#2"))])
    (root / "fixture.json").write_text(json.dumps(fixture))
    run(root / "dataset/kosgd2", root / "old.json", root / "selection.json", root / "fixture.json")
    base_cfg = dict(source=dict(dir="dataset/kosgd", dialogues_glob="dialogues_*.json"), group_key="dialogue_id",
                    pool=dict(kind="fixed_selection", path="old.json", field="selected_turns"))
    rules = dict(seed=20261012, dev_fraction=.2, sets=dict(kosgd=base_cfg))
    put_yaml(root / "configs/splits/rules.yaml", rules)
    value = read_yaml(root / "configs/sets/kosgd2.yaml")
    value["split_rules"] = dict(family="kosgd", source=dict(dir="dataset/kosgd2", dialogues_glob="dialogues_*.json"),
        group_key="dialogue_id", pool=dict(kind="fixed_selection", path="selection.json", field="selected_turns",
        exclude=[dict(path="old.json", field="selected_turns", by="dialogue_id"),
                 dict(path="fixture.json", field="cases", by="state_ref")]))
    put_yaml(root / "configs/sets/kosgd2.yaml", value)
    return rows, rules, fixture


def test_d1_rng_preservation_split_exclusion_and_family_union(tmp_path):
    rows, rules, fixture = prepare(tmp_path)
    expected, _ = select(rows, {"d0"})
    selected = json.loads((tmp_path / "selection.json").read_text())["selected_turns"]
    assert selected == [r for r in expected if r["dialogue_id"] != "d2"]
    for name in ("kosgd", "kosgd2"):
        item = entry(tmp_path, name)
        plan = _make_plan(name, item.split_rules, rules, tmp_path, item)
        write_split_plan(plan, tmp_path / f"configs/splits/{name}.json")
    sources = read_sources(tmp_path, ["kosgd", "kosgd2"])
    assert sources.pools["kosgd"] == sources.pools["kosgd2"] == {"d0", "d1", "d3", "d4"}
    for case in fixture["cases"]:
        assert resolve_source(case["state_ref"], sources)
    alias_only = read_sources(tmp_path, ["kosgd2"])
    assert alias_only.pools["kosgd2"] == sources.pools["kosgd"]
