"""무엇: T0 요청 순서/봉투/score 경계 · 입력: 합성 state/기존 render · 출력: 해시/거부 · 계약 T-a/b."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeveval.contract.request import check_request
from jeveval.t0.request import build_request
from jeveval.types import Request


@pytest.mark.parametrize("name", ["plain_text", "repeated_escaped", "klue_mrc", "functionchat", "kosgd"])
def test_existing_render_bytes(name):
    f = json.loads((Path(__file__).parents[1] / f"fixtures/render/{name}.json").read_text())
    data = f["input"]
    result = build_request(data["model"], data["state"], data["state_spec"], data["questions"])
    assert result.body["state"] == f["expected"]["state"]
    assert result.envelope_bytes.decode() == f["expected"]["request_utf8"]
    assert result.envelope_sha256 == f["expected"]["request_sha256"]
    assert result.target_end_char == f["expected"]["target_end_char"]


def test_alias_only_changes_envelope_and_detaches(response_fixture):
    questions = response_fixture["questions"]
    args = ("served", " \"줄\"\\\n한글 ", {"kind": "plain_text"}, questions)
    server = build_request(*args)
    ref = build_request(*args, reference_names={"served": "jev-latest"})
    assert server.request_sha256 == ref.request_sha256
    assert server.envelope_sha256 != ref.envelope_sha256
    assert list(server.body["questions"]["pick"]["criteria"]) == ["B", "A", "C"]
    assert build_request(*args, images=[]).request_sha256 == server.request_sha256
    assert build_request(*args, images=["image"]).request_sha256 != server.request_sha256
    questions["grade"]["criteria"][0] = "changed"
    assert server.body["questions"]["grade"]["criteria"][0] != "changed"
    with pytest.raises(NotImplementedError):
        check_request(Request(**server.body), "served")


@pytest.mark.parametrize("levels", [[], ["x"], ["x"] * 11, ["x", True], ["x", " "], {"0":"x","1":"y"}])
def test_score_criteria_rejected(response_fixture, levels):
    questions = deepcopy(response_fixture["questions"])
    questions["grade"]["criteria"] = levels
    with pytest.raises(ValueError):
        build_request("m", "s", {"kind":"plain_text"}, questions)


@pytest.mark.parametrize("n", [2, 10])
def test_score_supported_limits(response_fixture, n):
    question = dict(type="score", instructions="등급", criteria=[str(i) for i in range(n)])
    assert build_request("m", "s", {"kind":"plain_text"}, {"q": question}).body["questions"]["q"] == question
