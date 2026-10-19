"""독립 경로의 고정 연결·원 schema·R5/R6 경계와 import 제한."""

import ast
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from audits.audit_v4.independent import source, labels, timing, requests
from audits.audit_v4.independent.frozen import TABLES

ROOT = Path(__file__).resolve().parents[2]


def frame(intent="A", service="s", values=None):
    return dict(service=service, state=dict(active_intent=intent),
                actions=[dict(act="INFORM_INTENT", values=[intent] if values is None else values)])


def test_ast_and_shared_task_mutation_are_not_self_confirming():
    for p in (ROOT / "audits/audit_v4/independent").glob("*.py"):
        for n in ast.walk(ast.parse(p.read_text())):
            if isinstance(n, ast.Import): assert all(not x.name.startswith("jeveval") for x in n.names)
            if isinstance(n, ast.ImportFrom): assert not (n.module or "").startswith("jeveval")
    name = "kosgd2_full"
    payload = (ROOT / f"configs/tasks/{name}.yaml").read_bytes()
    task = yaml.safe_load(payload)
    assert requests.approved(task, name, payload)
    for key, value in (("role", "diagnostic"), ("label", "ongoing_slot_2")):
        wrong = deepcopy(task)
        wrong["questions"][0][key] = value
        assert not requests.approved(wrong, name, yaml.safe_dump(wrong).encode())


def test_schema_catalog_and_options_are_independently_ordered():
    cat = source.catalog([dict(service_name="s", description="S", intents=[dict(name="A", description="a")])])
    assert list(source.options(cat)) == ["s/A", "NONE"]
    corrupted_catalog = deepcopy(cat)
    corrupted_catalog[0]["intents"][0]["description"] = "corrupted"
    corrupted_options = source.options(corrupted_catalog)
    assert corrupted_catalog != cat and list(corrupted_options.items()) != list(source.options(cat).items())


def test_selection_consumes_t0_choice_before_exclusion():
    ds = {x: dict(turns=[dict(speaker="USER"), dict(speaker="USER")]) for x in ("a", "b", "c")}
    before = source.selected_again(ds, set(), set())
    assert source.selected_again(ds, set(), {"b"}) == [r for r in before if r["dialogue_id"] != "b"]
    with pytest.raises(ValueError): source.selected_again(ds, {"a"}, {"a"})


def test_full_and_actions_range_have_different_applicability():
    cat = [dict(service="s", intents=[dict(id="s/A")])]
    ds = {"d": dict(turns=[dict(frames=[frame("UNKNOWN")])])}
    selected = [dict(dialogue_id="d", turn_index=0)]
    assert labels.coverage(ds, selected, cat, "full", "kosgd2")["status"] == "FAIL"
    assert labels.coverage(ds, selected, cat, "actions_only", "kosgd2")["status"] == "PASS"
    ds["d"]["turns"][0]["frames"][0]["actions"][0]["act"] = "unknown"
    assert labels.coverage(ds, selected, cat, "actions_only", "kosgd2")["status"] == "FAIL"


def test_timing_exact_95_percent_malformed_and_empty_denominator():
    frames = [frame() for _ in range(20)]
    frames[-1] = frame(values=[])
    ds = {"d": dict(turns=[dict(speaker="USER", frames=frames)])}
    r = timing.check(ds)
    assert (r["status"], r["numerator"], r["denominator"], r["user_turns_scanned"]) == ("PASS", 19, 20, 1)
    frames[-2] = frame(values=["A", "B"])
    assert timing.check(ds)["status"] == "FAIL"
    assert timing.check({})["status"] == "INCOMPLETE"


def test_same_service_two_intents_is_incomplete_and_slots_are_ordered():
    cat = [dict(service="s", intents=[dict(id="s/B"), dict(id="s/A")])]
    turn = dict(frames=[frame("A"), frame("B"), frame("A")])
    ds = {"d": dict(turns=[turn])}
    selected = [dict(dialogue_id="d", turn_index=0)]
    assert labels.coverage(ds, selected, cat, "full", "kosgd2")["status"] == "INCOMPLETE"
    result = labels.gold(turn, cat, TABLES["kosgd2_full"])
    assert result["ongoing_1"]["gold"] == "s/B" and result["ongoing_2"]["gold"] == "s/A"
    assert result["ongoing_two"]["gold"] == "true"
    turn["frames"].append(frame("C"))
    assert labels.coverage(ds, selected, cat, "full", "kosgd2")["status"] == "FAIL"
