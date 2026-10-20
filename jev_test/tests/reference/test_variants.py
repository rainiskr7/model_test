"""참조 배치 라우팅, 질문 순서 및 위치 변형의 대상 보존."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from jeveval.reference import variants
from jeveval.reference.t0_runner import respond
from tests.t0_io.support import setup


@pytest.mark.parametrize("variant,count,index", [("single", 1, 0), ("eight_0", 8, 0),
    ("eight_7", 8, 7), ("seventeen_0", 17, 0), ("seventeen_7", 17, 7),
    ("seventeen_8", 17, 8), ("seventeen_15", 17, 15), ("seventeen_16", 17, 16)])
def test_placed_preserves_target_and_detaches_companions(variant, count, index):
    body = dict(model="m", state="target", images=["image"], questions={
        "companion_0": {"type": "choice", "criteria": {"B": "b", "A": "a"}}})
    companions = [dict(questions={"q": {"type": "noul", "instructions": "other"}})]
    before = deepcopy((body, companions))
    result = variants.placed(body, "companion_0", variant, companions)
    assert len(result["questions"]) == count
    assert list(result["questions"])[index] == "companion_0"
    assert result["questions"]["companion_0"] == body["questions"]["companion_0"]
    assert (result["state"], result["images"]) == (body["state"], body["images"])
    assert len(set(result["questions"])) == count
    result["questions"]["companion_0"]["criteria"].clear()
    result["images"].clear()
    assert (body, companions) == before


def test_placed_without_companions_uses_own_questions():
    body = dict(state="s", questions={"q": {"type": "noul"}})
    result = variants.placed(body, "q", "eight_7", [])
    assert list(result["questions"])[7] == "q"
    assert list(result["questions"].values()) == [{"type": "noul"}] * 8


@pytest.mark.parametrize("family", ["clef", "clef_flash", "pplx_v1"])
def test_batch_keeps_request_and_question_mapping(setup, family):
    ctx = setup(family)
    bodies = [dict(model="m", state=s, questions={"z": {"type": "noul"},
        "a": {"type": "choice", "criteria": {"B": "b", "A": "a"}}}) for s in ("first", "second")]
    before = deepcopy(bodies)
    result = variants.batch(ctx.runtime, bodies, 4)
    assert result == [respond(ctx.runtime, body) for body in bodies]
    assert all(list(row["answers"]) == ["z", "a"] for row in result)
    assert bodies == before
    if family == "pplx_v1":
        rows, size = ctx.runtime.model.model.calls[0]
        assert size == 4
        assert [r["state"] for r in rows] == ["first", "first", "second", "second"]


def test_unknown_batch_family_rejected():
    with pytest.raises(ValueError, match="^unsupported batch family$"):
        variants.batch(SimpleNamespace(family="unsupported"), [], 1)
