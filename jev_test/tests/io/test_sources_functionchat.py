"""무엇: FunctionChat 합성 원본 검사 · 입력: tmp_path JSONL · 출력: 구조 검증 · 계약 §6."""

import json

from jeveval.data.grouping import group_rows
from jeveval.io.sources.functionchat import read_rows


def test_system_first_nested_tools_and_transitive_components(tmp_path):
    rows = []
    for serial, content, tool in [(11, "첫 요청", "a"), (2, "첫 요청", "b"),
                                  (10, "다른 요청", "b"), (3, "독립 요청", "c")]:
        rows.append({"serial_num": serial, "input_messages": [
            {"role": "system", "content": "동일한 시스템"},
            {"role": "user", "content": content},
            {"role": "assistant", "content": "답"},
            {"role": "user", "content": "동일한 마지막 요청"}],
            "input_tools": [{"type": "function", "function": {
                "name": tool, "description": "도구", "parameters": {"type": "object"}}}]})
    path = tmp_path / "fc.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    loaded = read_rows({"file": "fc.jsonl"}, tmp_path)
    assert [r.fields for r in loaded] == rows
    assert group_rows(loaded, "fc_components").members == {"2": ["10", "11", "2"], "3": ["3"]}
    assert loaded[0].to_dict()["fields"]["input_tools"][0]["function"]["name"] == "a"
