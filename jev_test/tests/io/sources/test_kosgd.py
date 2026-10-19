"""무엇: KoSGD 합성 원본 검사 · 입력: tmp_path JSON · 출력: 행·선정 검증 · 계약 §6."""

import json

import pytest

from jeveval.io.sources.kosgd import read_rows, read_selection


def test_user_positions_and_sorted_files(tmp_path):
    frame = {"service": "서비스", "state": {"active_intent": "의도"}, "actions": []}
    turns = [{"speaker": "USER", "utterance": "원문", "frames": [frame]},
             {"speaker": "SYSTEM", "utterance": "응답", "frames": []},
             {"speaker": "USER", "utterance": "다음", "frames": []}]
    for number in [2, 1]:
        (tmp_path / f"dialogues_{number:03}.json").write_text(json.dumps([
            {"dialogue_id": f"d{number}", "services": ["서비스"], "turns": turns}]), encoding="utf-8")
    rows = read_rows({"dir": ".", "dialogues_glob": "dialogues_*.json"}, tmp_path)
    assert [r.row_id for r in rows] == ["d1#0", "d1#2", "d2#0", "d2#2"]
    assert rows[0].fields == {"dialogue_id": "d1", "turn_index": 0, "frames": [frame],
                              "services": ["서비스"], "dialogue": [dict(speaker="USER", utterance="원문")]}
    assert rows[1].fields["dialogue"] == [{k: t[k] for k in ("speaker", "utterance")} for t in turns]
    assert all("utterance" not in r.fields for r in rows)
    selected = [{"dialogue_id": "d1", "turn_index": 2}]
    (tmp_path / "audit.json").write_text(json.dumps({"selected_turns": selected, "ignored": 1}))
    assert read_selection({"path": "audit.json", "field": "selected_turns"}, tmp_path) == selected


def test_duplicate_dialogue_and_no_files(tmp_path):
    config = {"dir": ".", "dialogues_glob": "dialogues_*.json"}
    with pytest.raises(ValueError, match="no KoSGD"):
        read_rows(config, tmp_path)
    (tmp_path / "dialogues_001.json").write_text(json.dumps([
        {"dialogue_id": "d", "turns": []}, {"dialogue_id": "d", "turns": []}]))
    with pytest.raises(ValueError, match="duplicate dialogue"):
        read_rows(config, tmp_path)


def test_alias_stamps_source_set(tmp_path):
    path = tmp_path / "dialogues_1.json"
    path.write_text(json.dumps([dict(dialogue_id="d", services=[], turns=[
        dict(speaker="USER", utterance="private", frames=[])])]))
    rows = read_rows({"dir": ".", "dialogues_glob": "dialogues_*.json"}, tmp_path, set_name="kosgd2")
    assert rows[0].set == "kosgd2"


def test_exclusion_reader_validates_rule_and_collects_dialogue_ids(tmp_path):
    from jeveval.io.sources.kosgd import read_exclusions
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"selected_turns": [{"dialogue_id": "old", "turn_index": 0}]}))
    cfg = {"exclude": [{"path": "old.json", "field": "selected_turns", "by": "dialogue_id"}]}
    assert read_exclusions(cfg, tmp_path) == {"old"}
    cfg["exclude"][0]["by"] = "turn_index"
    with pytest.raises(ValueError):
        read_exclusions(cfg, tmp_path)


def test_fixture_exclusion_uses_dialogue_and_requires_fixture_schema(tmp_path):
    from jeveval.io.sources.kosgd import read_exclusions
    path = tmp_path / "fixture.json"
    data = dict(schema="t0_fixture/1", cases=[dict(state_ref=dict(set="kosgd", row_id="reserved#24"))])
    path.write_text(json.dumps(data))
    cfg = {"exclude": [{"path": "fixture.json", "field": "cases", "by": "state_ref"}]}
    assert read_exclusions(cfg, tmp_path) == {"reserved"}
    data["schema"] = "wrong"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="fixture"):
        read_exclusions(cfg, tmp_path)


def test_read_prefixes_never_requires_annotation_fields(tmp_path):
    import json
    from jeveval.io.sources.kosgd import read_prefixes
    path = tmp_path / "dialogues_001.json"
    path.write_text(json.dumps([dict(dialogue_id="d", turns=[dict(speaker="USER", utterance="synthetic")])]))
    result = read_prefixes(dict(dir=".", dialogues_glob="dialogues_*.json"), tmp_path,
                           [dict(dialogue_id="d", turn_index=0)])
    assert result[0].dialogue == (("USER", "synthetic"),)
