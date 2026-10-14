"""무엇: T0 합성 입력 · 입력: 고정 fixture · 출력: 독립 사본 · 계약 §8-7 T-c."""

import json
from pathlib import Path

import pytest

from jeveval.t0.request import build_request
from jeveval.types.t0 import T0Case, T0Observation, T0Tolerance


@pytest.fixture
def response_fixture():
    return json.loads((Path(__file__).parents[1] / "fixtures/t0/responses.json").read_text())


@pytest.fixture
def scenario(response_fixture):
    request = build_request("served", "private state", {"kind": "plain_text"}, response_fixture["questions"])
    case = T0Case("mixed", request, request.envelope_sha256)
    raw = json.dumps(response_fixture["valid"], ensure_ascii=False)
    observed = T0Observation("mixed", "a" * 64, request.request_sha256, request.envelope_sha256, 200, raw)
    tolerances = {"mixed": {qid: T0Tolerance("measured_zero", "PASS", 0, .0001, ["batch_1"], 5)
                            for qid in request.body["questions"]}}
    return case, observed, tolerances
