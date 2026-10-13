"""무엇: B1 전송 경계 · 입력: 기존 prompt fixture·토큰 ID · 출력: 본문·해시·멈춤 · 계약 §2-5·§5-5b."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from jeveval.client.vllm_chat import chat_body, chat_bytes, send_chat
from jeveval.contract.b1_prompt import build_b1_call
from jeveval.types import AttemptResult, B1Config, BoundQuestion, Rendered


def call():
    fixture = json.loads((Path(__file__).parents[1] / "fixtures/b1/prompt.json").read_text())
    case = fixture["cases"][0]
    return build_b1_call(B1Config.from_dict(fixture["config"]), Rendered.from_dict(fixture["rendered"]),
                         BoundQuestion.from_dict(case["question"]), case["call_qid"])


def test_body_order_params_copies_and_send_hash():
    source = call()
    before = deepcopy(source)
    body = chat_body(source, "served", {"Z": 30, "X": 10, "Y": 20})
    assert body == {"model": "served", "messages": source.messages, **source.params,
                    "allowed_token_ids": [10, 20, 30]}
    expected = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    assert chat_bytes(body) == expected
    result = AttemptResult("start", "end", 0.0, 200, None, None, "{}")
    calls = []

    def post(url, payload, timeout):
        calls.append((url, payload, timeout))
        return result

    digest, received = send_chat("http://127.0.0.1:9/", body, post=post)
    assert calls == [("http://127.0.0.1:9/v1/chat/completions", expected, 600)]
    assert digest == hashlib.sha256(expected).hexdigest() and received is result
    body["messages"].clear()
    body["chat_template_kwargs"]["enable_thinking"] = True
    assert source == before


@pytest.mark.parametrize("ids", [{"X": 1}, {"X": 1, "Y": 1, "Z": 2},
                                 {"X": True, "Y": 2, "Z": 3}])
def test_missing_duplicate_and_bool_tokens(ids):
    with pytest.raises(ValueError):
        chat_body(call(), "m", ids)


@pytest.mark.parametrize("key", ["model", "messages", "allowed_token_ids"])
def test_reserved_params_stop(key):
    source = call()
    source.params[key] = None
    with pytest.raises(ValueError):
        chat_body(source, "m", {"X": 1, "Y": 2, "Z": 3})
