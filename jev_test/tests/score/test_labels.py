"""무엇: 정답 규칙 검사 · 입력: 합성 SourceRow · 출력: 클래스·엄격 오류 대조 · 계약 §6-2."""

from copy import deepcopy
from pathlib import Path

import pytest

from jeveval.io.datasets import read_label_vocab
from jeveval.score.labels import gold

from jeveval.types import SourceRow

VOCAB = read_label_vocab(Path(__file__).resolve().parents[2] / "configs/datasets.yaml")


def row(**fields):
    return SourceRow("synthetic", "0", fields)


@pytest.mark.parametrize("act", VOCAB.kosgd_acts)
def test_every_act_positive_negative_and_close(act, label_rules):
    label = "act:" + ("CLOSE" if act in ("GOODBYE", "THANK_YOU") else act)
    rows = [row(frames=[{"actions": [{"act": act}]}])]
    assert gold(label, rows, {}, None, label_rules) == "true"
    assert gold(label, [row(frames=[{"actions": []}])], {}, None, label_rules) == "false"


def test_unknown_act_and_missing_actions_fail(label_rules):
    for frames in [[{"actions": [{"act": "OTHER"}]}], [{}], [{"actions": None}]]:
        with pytest.raises(ValueError):
            gold("act:CLOSE", [row(frames=frames)], {}, None, label_rules)


def test_slots_use_catalog_order_service_and_deduplicate(label_rules):
    frames = [{"service": s, "state": {"active_intent": "same"}} for s in ["a", "z", "a"]]
    options = {"z/same": "z", "a/same": "a", "NONE": "none"}
    before = deepcopy((frames, options))
    assert [gold(f"ongoing_slot_{i}", [row(frames=frames)], {}, options, label_rules)
            for i in [1, 2]] == ["z/same", "a/same"]
    assert (frames, options) == before
    for frames, expected in [([], ["NONE", "NONE"]),
            ([{"service": "a", "state": {"active_intent": "same"}}], ["a/same", "NONE"])]:
        assert [gold(f"ongoing_slot_{i}", [row(frames=frames)], {}, options, label_rules)
                for i in [1, 2]] == expected
    with pytest.raises(ValueError):
        gold("ongoing_slot_1", [row(frames=before[0])], {}, {"NONE": "none"}, label_rules)


@pytest.mark.parametrize("action", ["call", "slot", "relevance"])
def test_fc_rules(action, label_rules):
    truth = {"tool_calls": [{"function": {"name": "tool"}}]} if action == "call" else {}
    rows = [row(type_of_output=action, ground_truth=truth)]
    assert gold("fc:type_of_output", rows, {}, None, label_rules) == action
    assert gold("fc:tool", rows, {}, {"tool": "t", "NONE": "n"}, label_rules) == (
        "tool" if action == "call" else "NONE")


@pytest.mark.parametrize("action,truth", [
    ("call", {"tool_calls": []}), ("call", {"tool_calls": [{}, {}]}),
    ("call", {"tool_calls": [{"function": {"name": "outside"}}]}),
    ("slot", {"tool_calls": []}), ("relevance", {"tool_calls": None}),
    ("call", {}), ("bad", {}), (None, {}), ("call", None)])
def test_fc_invalid(action, truth, label_rules):
    with pytest.raises(ValueError):
        gold("fc:tool", [row(type_of_output=action, ground_truth=truth)], {}, {"NONE": "n"}, label_rules)


@pytest.mark.parametrize("prefix,field,names", [
    ("kmhas", "label_names", VOCAB.kmhas), ("kote", "labels_majority", VOCAB.kote)])
def test_every_membership_rule(prefix, field, names, label_rules):
    for name in names:
        assert gold(prefix + ":" + name, [row(**{field: [name]})], {}, None, label_rules) == "true"
        assert gold(prefix + ":" + name, [row(**{field: []})], {}, None, label_rules) == "false"
        for value in (None, name, [1]):
            with pytest.raises(ValueError):
                gold(prefix + ":" + name, [row(**{field: value})], {}, None, label_rules)


def test_korfin_binding_and_klue_boolean(label_rules):
    rows = [row(ASPECT="a", SENTIMENT="POSITIVE"), row(ASPECT="b", SENTIMENT="NEGATIVE")]
    for aspect, expected in [("a", "POSITIVE"), ("b", "NEGATIVE")]:
        assert gold("korfin:sentiment", rows, {"ASPECT": aspect}, {}, label_rules) == expected
    for value, expected in [(False, "true"), (True, "false")]:
        assert gold("klue:answerable", [row(is_impossible=value)], {}, None, label_rules) == expected
    for value in (0, 1, "false", None):
        with pytest.raises(ValueError):
            gold("klue:answerable", [row(is_impossible=value)], {}, None, label_rules)


def test_all_rules_reject_missing_fields_and_unknown_name(label_rules):
    assert len(label_rules) == 33
    for label in [*label_rules, "unknown:name"]:
        with pytest.raises(ValueError):
            gold(label, [row()], {}, {}, label_rules)
