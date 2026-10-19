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
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps(dict(schema="t0_fixture/1", cases=[dict(state_ref=dict(set="kosgd", row_id="t0#0"))])))
    rows = json.loads(source.read_text())
    rows.append(dict(dialogue_id="t0", turns=[dict(speaker="USER")]))
    source.write_text(json.dumps(rows))
    old.write_text('{"selected_turns": []}')
    assert run(tmp_path, old, out, fixture) == dict(G=1, n_without_user=0, intersection=0)
    assert "PRIVATE_RAW" not in out.read_text()
    assert json.loads(out.read_text())["excluded_source"] == "kosgd"
    with pytest.raises(ValueError):
        run(tmp_path, old, out, fixture)


def test_t0_exclusion_filters_results_after_rng_consumption():
    import random
    from audits.kosgd2_selection.select_turns import SEED
    rows = [dict(dialogue_id=f"d{i:03d}", turns=[dict(speaker="USER") for _ in range(2 + i % 9)])
            for i in range(80)]
    old, held_out = {"d000"}, {"d005", "d030", "d079"}
    before, missing = select(rows, old)
    after, new_missing = select(list(reversed(rows)), old, held_out)
    assert missing == new_missing == 0
    assert after == [r for r in before if r["dialogue_id"] not in held_out]
    rng = random.Random(SEED)
    expected = [dict(dialogue_id=d["dialogue_id"], turn_index=rng.choice(range(len(d["turns"]))))
                for d in rows if d["dialogue_id"] not in old]
    assert before == expected
    with pytest.raises(ValueError, match="T0 dialogue intersects"):
        select(rows, old, old)
    with pytest.raises(ValueError, match="T0 dialogue missing"):
        select(rows, old, {"missing"})


def test_missing_or_invalid_t0_fixture_never_writes_selection(tmp_path):
    source = tmp_path / "dialogues_1.json"
    source.write_text(json.dumps([dict(dialogue_id="d", turns=[dict(speaker="USER")])]))
    old, fixture, out = (tmp_path / n for n in ("old.json", "fixture.json", "out.json"))
    old.write_text('{"selected_turns": []}')
    for value in ({}, dict(schema="t0_fixture/1", cases=[]),
                  dict(schema="t0_fixture/1", cases=[dict(state_ref=dict(set="kosgd", row_id="missing#0"))])):
        fixture.write_text(json.dumps(value))
        with pytest.raises(ValueError):
            run(tmp_path, old, out, fixture)
        assert not out.exists()
