"""무엇: T0 참조 제외 · 입력: 합성 state_ref · 출력: 가족 대화 단위 집합 · 계약 판 5 보정 1 §6-2."""

import pytest

from jeveval.data.exclusions import dialogue_ids


def test_only_kosgd_family_refs_are_excluded_at_dialogue_level():
    cases = [dict(state_ref=dict(set=s, row_id=r)) for s, r in
             [("kosgd", "d#0"), ("kosgd2", "d#2"), ("kmhas", "123")]]
    assert dialogue_ids(cases + [{"synthetic_state": "x"}], "state_ref") == {"d"}
    assert dialogue_ids([{"dialogue_id": "d", "turn_index": 0}], "dialogue_id") == {"d"}


@pytest.mark.parametrize("records,by", [(None, "state_ref"), ([None], "state_ref"),
    ([{"state_ref": None}], "state_ref"), ([{"dialogue_id": ""}], "dialogue_id"),
    ([{"state_ref": {"set": "kosgd", "row_id": "d#bad"}}], "state_ref"), ([], "unknown")])
def test_invalid_exclusion_evidence_rejected(records, by):
    with pytest.raises(ValueError):
        dialogue_ids(records, by)
