"""무엇: 6셋 텍스트 투영·API 경계. 입력: 합성 SourceRow. 출력: 필드·중복·manifest 단언."""

import pytest

from audits.publish_check.sources import SETS, fields, normalized, project, source_sets
from jeveval.types import SourceRow


@pytest.mark.parametrize("name,value,expected", [
    ("kosgd", dict(dialogue_id="d", dialogue=[dict(utterance="first"), dict(utterance="second")]), ["first", "second"]),
    ("fc_call_decision", dict(input_messages=[dict(content="message")],
        input_tools=[dict(function=dict(description="tool", parameters=dict(description="parameter")))]), ["message", "tool", "parameter"]),
    ("kmhas", dict(text="sentence"), ["sentence"]),
    ("kote_escalation", dict(text="emotion"), ["emotion"]),
    ("korfin_asc", dict(SRC="financial", ASPECT="aspect"), ["financial", "aspect"]),
    ("klue_mrc_answerable", dict(context="context", question="question", answers=dict(text=["answer"])), ["context", "question", "answer"]),
])
def test_fields(name, value, expected):
    row = SourceRow(name, "synthetic-id", value)
    assert [v for _, _, v in fields(name, row)] == expected


def test_nfc_spaces_deduplicate_and_keep_origins():
    docs, manifest = project("kmhas", [
        SourceRow("kmhas", "one", dict(text="가 나\t다\n라마바사아자차카타파하")),
        SourceRow("kmhas", "two", dict(text="가나다라마바사아자차카타파하")),
    ], 12)
    assert len(docs) == 1
    assert docs[0].origins == [("one", "text"), ("two", "text")]
    assert manifest["rows"] == 2 and manifest["windows"] == 3
    assert normalized("가\u2003나") == "가나"


def test_reader_api_loads_all_sets_without_pool_or_split(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from jeveval.io import set_config, sources
    seen = []
    def entry(root, name):
        assert root == tmp_path
        return SimpleNamespace(split_rules={"source": {"synthetic": True}})
    def read(name, rules, root, *, selected):
        assert rules is selected.split_rules and root == tmp_path
        seen.append(name)
        return [SourceRow(name, "row", {})]
    monkeypatch.setattr(set_config, "entry", entry)
    monkeypatch.setattr(sources, "read_set_rows", read)
    monkeypatch.setattr("audits.publish_check.sources.fields", lambda name, row: [("row", "text", "synthetic original string")])
    loaded = list(source_sets(tmp_path, 12))
    assert seen == list(SETS) and len(loaded) == 6
    assert all(m["rows"] == 1 for _, _, m in loaded)
