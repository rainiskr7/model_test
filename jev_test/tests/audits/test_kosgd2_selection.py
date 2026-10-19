"""무엇: 새 풀 선정 경계 · 입력: 합성 대화 · 출력: 결정성·제외·비공개 · 개정 15."""

import json

import pytest

from audits.kosgd2_selection.select_turns import run, select


def test_sorted_rng_selection_and_exclusion_are_deterministic():
    dialogues = [dict(dialogue_id=i, turns=[dict(speaker=s) for s in speakers]) for i, speakers in
                 [("b", ["USER", "SYSTEM", "USER"]), ("a", ["USER"]), ("c", ["SYSTEM"])]]
    a, missing = select(dialogues, {"a"})
    assert (a, missing) == select(list(reversed(dialogues)), {"a"})
    assert a[0]["dialogue_id"] == "b" and missing == 1
    with pytest.raises(ValueError):
        select(dialogues, {"unknown"})


def test_selection_output_contains_ids_hashes_not_utterances(tmp_path):
    source = tmp_path / "dialogues_1.json"
    source.write_text(json.dumps([dict(dialogue_id="d", turns=[dict(speaker="USER", utterance="PRIVATE_RAW")])]))
    old, out = tmp_path / "old.json", tmp_path / "selection.json"
    old.write_text('{"selected_turns": []}')
    assert run(tmp_path, old, out) == dict(G=1, n_without_user=0, intersection=0)
    assert "PRIVATE_RAW" not in out.read_text()
    assert json.loads(out.read_text())["excluded_source"] == "kosgd"
    with pytest.raises(ValueError):
        run(tmp_path, old, out)
