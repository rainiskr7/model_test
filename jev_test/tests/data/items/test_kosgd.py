"""무엇: KoSGD 항목 검사 · 입력: 합성 USER 행 · 출력: state·고정 칸·직전 기준선 · 계약 §6-2."""

from copy import deepcopy
from dataclasses import replace

import pytest

from jeveval.data.items.kosgd import build_items
from jeveval.types import SourceRow


def _row(did, index, intent):
    frames = [{"service": "z", "state": {"active_intent": intent}, "actions": [{"act": "INFORM"}]}]
    return SourceRow("kosgd", f"{did}#{index}", dict(dialogue_id=did, turn_index=index,
        frames=frames, services=["z"], dialogue=[{"speaker": "USER", "utterance": f"u{index}"}]))


@pytest.mark.parametrize("variant", ["kosgd_full", "kosgd_actions_only"])
def test_previous_user_not_previous_item_both_variants(settings, plan_for, variant, label_rules):
    task, _ = settings(variant)
    lists = {"kosgd_catalog": [{"service": "z", "intents": [{"id": "z/old"}, {"id": "z/new"}]}],
             "catalog_intents_plus_none": {"z/old": "old", "z/new": "new", "NONE": "none"}}
    rows = [_row("d2", 4, "new"), _row("d1", 0, "old"), _row("d2", 0, "NONE"), _row("d2", 2, "old")]
    plan = plan_for(rows, task, {"d2": "kosgd:d2:4"})
    before = deepcopy((rows, plan, task, lists))
    result = build_items(rows, plan, task, lists, label_rules)
    assert result["extra"] == []
    assert result["dev"][0].baseline == {"copy_prev": ["NONE", "NONE"]}
    item = result["test"][0]
    assert (item.set, item.group_id, item.item_id) == ("kosgd", "d2", "4")
    assert item.baseline == {"copy_prev": ["z/old", "NONE"]}
    assert item.meta == dict(service=["z"], stratum=None, flags=[])
    assert item.state_fields == dict(dialogue=rows[0].fields["dialogue"], catalog=lists["kosgd_catalog"])
    if variant == "kosgd_full":
        assert [q.gold for q in item.questions[:2]] == ["z/new", "NONE"]
    item.state_fields["catalog"].clear()
    item.meta["service"].clear()
    assert (rows, plan, task, lists) == before


def test_catalog_and_group_mismatch_stop(settings, plan_for, label_rules):
    task, lists = settings("kosgd_full")
    rows = [_row("d", 0, "NONE")]
    plan = plan_for(rows, task)
    bad = deepcopy(lists)
    bad["catalog_intents_plus_none"] = dict(reversed(list(bad["catalog_intents_plus_none"].items())))
    with pytest.raises(ValueError, match="catalog"):
        build_items(rows, plan, task, bad, label_rules)
    plan = replace(plan, groups={"d": ["0", "2"]})
    with pytest.raises(ValueError, match="plan.groups"):
        build_items(rows, plan, task, lists, label_rules)
