"""무엇: T0 요청·동일성 해시 · 입력: state 설정/세 종류 질문 · 출력: T0Request · 계약 §8-7 T-a/b."""

from copy import deepcopy
from hashlib import sha256
import json
import re

from jeveval.contract.render import render_state
from jeveval.contract.request import check_request
from jeveval.types import Request
from jeveval.types.t0 import T0Request


def canonical_bytes(value, *, sort_keys=False):
    """요청은 삽입 순서 보존, 설정 해시는 키 정렬. UTF-8·공백 없는 JSON이다."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      sort_keys=sort_keys, allow_nan=False).encode("utf-8")


def _check_questions(questions, model, state):
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty object")
    for qid, question in questions.items():
        if not isinstance(question, dict) or set(question) != {"type", "instructions", "criteria"}:
            raise ValueError("invalid question fields")
        if question["type"] != "score":
            if check_request(Request(model, state, {qid: question}), model):
                raise ValueError("invalid noul/choice request")
            continue
        if not isinstance(qid, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", qid):
            raise ValueError("invalid question ID")
        levels, instructions = question["criteria"], question["instructions"]
        if not isinstance(instructions, str) or not instructions.strip():
            raise ValueError("invalid score instructions")
        if (not isinstance(levels, list) or not 2 <= len(levels) <= 10
                or any(not isinstance(s, str) or not s.strip() for s in levels)):
            raise ValueError("score criteria must contain 2..10 nonempty strings")


def build_request(model, state_fields, state_spec, questions, *, images=None, reference_names=None):
    """model 대응은 봉투에만 적용한다. 동일성 해시는 state/questions/images 순서다."""
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model is required")
    rendered = render_state(state_fields, state_spec)
    _check_questions(questions, model, rendered.state)
    name = model if reference_names is None else reference_names.get(model, model)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("invalid reference model name")
    identity = dict(state=rendered.state, questions=deepcopy(questions))
    body = dict(model=name, **identity)
    if images is not None:
        if not isinstance(images, list) or any(not isinstance(s, str) or not s for s in images):
            raise ValueError("images must be a list of strings")
        body["images"] = deepcopy(images)
    identity["images"] = deepcopy(images) if images is not None else []
    payload = canonical_bytes(body)
    return T0Request(body, payload, sha256(payload).hexdigest(),
                     sha256(canonical_bytes(identity)).hexdigest(), rendered.target_end_char)
