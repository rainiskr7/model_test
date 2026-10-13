"""무엇: 렌더·요청 경계 검증 · 입력: 기존 render fixture · 출력: 바이트/위치 대조 · 계약 §2."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeveval.contract.render import render_state
from jeveval.contract.request import build_request, check_request, request_bytes, request_sha256
from jeveval.types import BoundQuestion


ROOT = Path(__file__).parents[1] / "fixtures/render"


@pytest.mark.parametrize("path", sorted(ROOT.glob("*.json")), ids=lambda p: p.stem)
def test_render_request_fixture(path):
    fixture = json.loads(path.read_text())
    source, expected = fixture["input"], fixture["expected"]
    before = deepcopy(source)
    rendered = render_state(source["state"], source["state_spec"])
    assert rendered.state == expected["state"]
    assert rendered.target_end_char == expected["target_end_char"]
    questions = [BoundQuestion(qid, "success", q["type"], q["instructions"],
        q["criteria"] if q["type"] == "choice" else None,
        q["criteria"] if q["type"] == "noul" else None, "synthetic", None)
        for qid, q in source["questions"].items()]
    request = build_request(source["model"], rendered, questions)
    assert check_request(request, source["model"]) == []
    assert request_bytes(request) == expected["request_utf8"].encode("utf-8")
    assert request_sha256(request) == expected["request_sha256"]
    assert source == before


@pytest.mark.parametrize("fields,keys,target", [
    ({"a": "x", "extra": 1}, ["a"], "a"), ({}, ["a"], "a"),
    ({"a": "x"}, ["a", "a"], "a"), ({"a": []}, ["a"], "a"),
])
def test_invalid_state(fields, keys, target):
    with pytest.raises(ValueError):
        render_state(fields, dict(kind="json_string", keys=keys, target_key=target))


def test_unicode_key_and_escaped_target_before_repeated_tail():
    fields = {"끝": '"대상"\\\n', "tail": '"대상"\\\n'}
    rendered = render_state(fields, dict(kind="json_string", keys=["끝", "tail"], target_key="끝"))
    prefix = '{"끝":' + json.dumps(fields["끝"], ensure_ascii=False)
    assert rendered.state[:rendered.target_end_char] == prefix
    assert rendered.target_end_char == len(prefix)


def test_plain_text_keeps_whitespace():
    rendered = render_state(" \n가😀 ", {"kind": "plain_text"})
    assert rendered.state == " \n가😀 " and rendered.target_end_char == 5
