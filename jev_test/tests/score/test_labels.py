"""무엇: 정답 규칙 검사 · 입력: 합성 SourceRow · 출력: 클래스·엄격 오류 대조 · 계약 §6-2."""

from copy import deepcopy

import pytest

from jeveval.score.labels import ACTS, KMHAS, KOTE, RULES, gold
from jeveval.types import SourceRow


def row(**fields):
    return SourceRow("synthetic", "0", fields)


@pytest.mark.parametrize("act", ACTS)
def test_every_act_positive_negative_and_close(act):
    label = "act:" + ("CLOSE" if act in ("GOODBYE", "THANK_YOU") else act)
    rows = [row(frames=[{"actions": [{"act": act}]}])]
    assert gold(label, rows, {}, None) == "true"
    assert gold(label, [row(frames=[{"actions": []}])], {}, None) == "false"


def test_unknown_act_and_missing_actions_fail():
    for frames in [[{"actions": [{"act": "OTHER"}]}], [{}], [{"actions": None}]]:
        with pytest.raises(ValueError):
            gold("act:CLOSE", [row(frames=frames)], {}, None)


def test_slots_use_catalog_order_service_and_deduplicate():
    frames = [{"service": s, "state": {"active_intent": "same"}} for s in ["a", "z", "a"]]
    options = {"z/same": "z", "a/same": "a", "NONE": "none"}
    before = deepcopy((frames, options))
    assert [gold(f"ongoing_slot_{i}", [row(frames=frames)], {}, options)
            for i in [1, 2]] == ["z/same", "a/same"]
    assert (frames, options) == before
    for frames, expected in [([], ["NONE", "NONE"]),
            ([{"service": "a", "state": {"active_intent": "same"}}], ["a/same", "NONE"])]:
        assert [gold(f"ongoing_slot_{i}", [row(frames=frames)], {}, options)
                for i in [1, 2]] == expected
    with pytest.raises(ValueError):
        gold("ongoing_slot_1", [row(frames=before[0])], {}, {"NONE": "none"})


@pytest.mark.parametrize("action", ["call", "slot", "relevance"])
def test_fc_rules(action):
    truth = {"tool_calls": [{"function": {"name": "tool"}}]} if action == "call" else {}
    rows = [row(type_of_output=action, ground_truth=truth)]
    assert gold("fc:type_of_output", rows, {}, None) == action
    assert gold("fc:tool", rows, {}, {"tool": "t", "NONE": "n"}) == (
        "tool" if action == "call" else "NONE")


@pytest.mark.parametrize("action,truth", [
    ("call", {"tool_calls": []}), ("call", {"tool_calls": [{}, {}]}),
    ("call", {"tool_calls": [{"function": {"name": "outside"}}]}),
    ("slot", {"tool_calls": []}), ("relevance", {"tool_calls": None}),
    ("call", {}), ("bad", {}), (None, {}), ("call", None)])
def test_fc_invalid(action, truth):
    with pytest.raises(ValueError):
        gold("fc:tool", [row(type_of_output=action, ground_truth=truth)], {}, {"NONE": "n"})


@pytest.mark.parametrize("prefix,field,names", [
    ("kmhas", "label_names", KMHAS), ("kote", "labels_majority", KOTE)])
def test_every_membership_rule(prefix, field, names):
    for name in names:
        assert gold(prefix + ":" + name, [row(**{field: [name]})], {}, None) == "true"
        assert gold(prefix + ":" + name, [row(**{field: []})], {}, None) == "false"
        for value in (None, name, [1]):
            with pytest.raises(ValueError):
                gold(prefix + ":" + name, [row(**{field: value})], {}, None)


def test_korfin_binding_and_klue_boolean():
    rows = [row(ASPECT="a", SENTIMENT="POSITIVE"), row(ASPECT="b", SENTIMENT="NEGATIVE")]
    for aspect, expected in [("a", "POSITIVE"), ("b", "NEGATIVE")]:
        assert gold("korfin:sentiment", rows, {"ASPECT": aspect}, {}) == expected
    for value, expected in [(False, "true"), (True, "false")]:
        assert gold("klue:answerable", [row(is_impossible=value)], {}, None) == expected
    for value in (0, 1, "false", None):
        with pytest.raises(ValueError):
            gold("klue:answerable", [row(is_impossible=value)], {}, None)


def test_all_rules_reject_missing_fields_and_unknown_name():
    assert len(RULES) == 33
    for label in [*RULES, "unknown:name"]:
        with pytest.raises(ValueError):
            gold(label, [row()], {}, {})
