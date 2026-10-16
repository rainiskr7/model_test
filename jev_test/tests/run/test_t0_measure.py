"""T0 길이 어댑터와 경계 요청 생성의 보존·정확 길이 계약."""

from copy import deepcopy

import pytest

from jeveval.run.t0_measure import boundary_builder_with, measure_with
from jeveval.t0.request import build_request
from jeveval.types import LengthInfo


class CharacterMeasurer:
    def __init__(self):
        self.plans = []

    def measure(self, plan):
        self.plans.append(plan)
        return LengthInfo(len(plan.request.state) + 3, plan.rendered.target_end_char, 100, 3)


@pytest.fixture
def base_request():
    return build_request("m", "state", {"kind": "plain_text"}, {"q": {"type": "noul", "instructions": "ready?",
        "criteria": {"true": "yes", "false": "no"}}})


def test_measure_adapter_preserves_request_and_rendered_target(base_request):
    measurer = CharacterMeasurer()
    assert measure_with(measurer)(base_request) == 8
    plan, = measurer.plans
    assert plan.kind == "systemone" and plan.question_ids == ["q"]
    assert plan.body == base_request.envelope_bytes and plan.request_sha256 == base_request.request_sha256
    assert plan.request.to_dict() == base_request.body
    assert plan.rendered.state == "state" and plan.rendered.target_end_char == base_request.target_end_char
    plan.request.questions.clear()
    assert base_request.body["questions"] == {"q": {"type": "noul", "instructions": "ready?",
        "criteria": {"true": "yes", "false": "no"}}}


@pytest.mark.parametrize("target", [9, 10, 31])
def test_boundary_builder_hits_exact_length_and_preserves_request(base_request, target):
    before = deepcopy(base_request.body)
    measurer = CharacterMeasurer()
    result, lengths = boundary_builder_with(measurer)(base_request, target)
    assert lengths == [target] and measure_with(measurer)(result) == target
    assert result.body["state"].startswith(base_request.body["state"])
    assert result.body["questions"] == base_request.body["questions"] and result.body["model"] == "m"
    assert base_request.body == before


def test_boundary_already_at_target_is_valid(base_request):
    measurer = CharacterMeasurer()
    result, lengths = boundary_builder_with(measurer)(base_request, 8)
    assert lengths == [8] and measure_with(measurer)(result) == 8


@pytest.mark.parametrize("target", [0, -1, True, 1.5])
def test_boundary_target_requires_positive_integer(base_request, target):
    with pytest.raises(ValueError, match="^target length must be a positive integer$"):
        boundary_builder_with(CharacterMeasurer())(base_request, target)


def test_boundary_cannot_shorten_base_request(base_request):
    with pytest.raises(ValueError, match="^base request already exceeds the target length$"):
        boundary_builder_with(CharacterMeasurer())(base_request, 7)
