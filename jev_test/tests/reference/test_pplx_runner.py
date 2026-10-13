"""무엇: pplx 버전별 seam · 입력: 가짜 참조/temperature fixture · 출력: 확률 한 번/원 답 · 계약 R1."""

from copy import deepcopy
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

from jeveval.reference import pplx_runner
from tests.reference import fake_server

TEMPERATURE = json.loads((Path(__file__).parents[1] / "fixtures/temperature/pplx_path.json").read_text())


@pytest.mark.parametrize("case", TEMPERATURE["cases"])
def test_v11_server_boundary_applies_temperature_once(case, monkeypatch):
    module, package = ModuleType("autojev.model"), ModuleType("autojev")
    module.answer = lambda question, values: dict(type="choice", choice="b", confidence=values[1],
        probabilities=dict(zip(question["criteria"], values)))
    monkeypatch.setitem(sys.modules, "autojev", package)
    monkeypatch.setitem(sys.modules, "autojev.model", module)
    model = fake_server.FixedModel(case["logits"], TEMPERATURE["temperature"])
    request = dict(model="autojev", state="synthetic", questions={
        str(i): {"type": "choice", "criteria": {"a": "A", "b": "B"}} for i in range(17)})
    before = deepcopy(request)
    response = pplx_runner.respond_v11(model, request, server=fake_server)
    assert [len(rows) for rows in model.batches] == [8, 8, 1]
    assert response["usage"] == dict(input_tokens=51, output_tokens=0)
    assert response["model"] == "reference-service" and request == before
    for value in response["answers"].values():
        assert value["choice"] == "b" and value["confidence"] == value["probabilities"]["b"]
        probs = list(value["probabilities"].values())
        assert probs == pytest.approx(case["expected"], abs=TEMPERATURE["comparison_atol"], rel=0)
        for wrong in ("zero_applications", "two_applications"):
            if case[wrong] != case["expected"]:
                assert probs != pytest.approx(case[wrong], abs=TEMPERATURE["comparison_atol"], rel=0)


def test_v1_calls_one_question_and_preserves_calibrated_answers():
    calls = []
    choice = dict(type="choice", choice="b", confidence=.40003, probabilities=dict(a=.59997, b=.40003))
    noul = dict(type="noul", noul=.1234)
    expected = dict(first=noul, second=choice)
    def predict(state, question, *, images):
        calls.append((state, question, images))
        return noul if question["type"] == "noul" else choice
    request = dict(model="v1", state="state", questions={"first": {"type": "noul"},
                   "second": {"type": "choice", "criteria": {"a": "A", "b": "B"}}}, images=["local"])
    result = pplx_runner.respond_v1(SimpleNamespace(predict=predict), request)
    assert result == dict(model="v1", answers=expected)
    assert list(result["answers"]) == ["first", "second"]
    assert [q for _, q, _ in calls] == list(request["questions"].values())
    assert all(state == "state" and images == ["local"] for state, _, images in calls)
    assert all(value is expected[key] for key, value in result["answers"].items())


@pytest.mark.parametrize("loader", [pplx_runner.load_v1, pplx_runner.load_v11])
def test_loaders_require_local_checkpoint_before_reference_call(tmp_path, loader):
    with pytest.raises(ValueError, match="local checkpoint"):
        loader(tmp_path / "missing", reference=object())


def test_loaders_force_offline_and_pass_local_path(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    calls = []
    def construct(**kwargs):
        assert os.environ["HF_HUB_OFFLINE"] == os.environ["TRANSFORMERS_OFFLINE"] == "1"
        calls.append(kwargs)
        return "loaded"
    decider = SimpleNamespace(from_pretrained=lambda path, **kw: construct(checkpoint=path, **kw))
    assert pplx_runner.load_v1(tmp_path, device="cpu", reference=SimpleNamespace(Decider=decider)) == "loaded"
    assert pplx_runner.load_v11(tmp_path, device="cpu", reference=SimpleNamespace(DecisionModel=construct)) == "loaded"
    assert calls == [dict(checkpoint=str(tmp_path), device="cpu"), dict(checkpoint=tmp_path, device="cpu")]


def test_v11_default_server_import_is_lazy_and_delegated(monkeypatch):
    package = ModuleType("autojev")
    expected = {"reference": "unmodified"}
    package.server = SimpleNamespace(EvaluationRequest=lambda **kw: kw, predict=lambda model, body: expected)
    monkeypatch.setitem(sys.modules, "autojev", package)
    assert pplx_runner.respond_v11(object(), {"state": "state"}) is expected
