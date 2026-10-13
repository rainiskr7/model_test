"""무엇: Clef 전체 요청 위임 · 입력: 로컬 폴더/가짜 참조 · 출력: 원 답/오프라인 · 계약 §8-6 H·I."""

from copy import deepcopy
import os
from types import SimpleNamespace

import pytest

from jeveval.reference import clef_runner


def test_load_requires_directory_and_forces_offline(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="local checkpoint"):
        clef_runner.load(tmp_path / "missing", reference=object())
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    def load(path, **kwargs):
        assert path == tmp_path and kwargs == dict(device="cpu", local_files_only=True)
        assert os.environ["HF_HUB_OFFLINE"] == os.environ["TRANSFORMERS_OFFLINE"] == "1"
        return "model", "processor"
    reference = SimpleNamespace(load_release_model=load)
    assert clef_runner.load(tmp_path, device="cpu", reference=reference) == (reference, "model", "processor")


@pytest.mark.parametrize("name", ["clef", "clef-flash"])
def test_whole_request_and_reference_rounding_choice_preserved(name):
    request = dict(model=name, state=" state ", questions={"q": {"type": "noul"}}, images=[])
    before = deepcopy(request)
    expected = dict(answers={"q": {"noul": .1234}}, usage={"input_tokens": 7})
    def systemone(model, processor, body, *, max_length):
        assert model == "m" and processor == "p" and body is request and max_length == 19
        return expected
    reference = SimpleNamespace(systemone=systemone)
    assert clef_runner.respond(reference, "m", "p", request, max_length=19) is expected
    assert request == before


def test_default_loader_uses_checkpoint_reference_without_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    source = tmp_path / "joint_schema_model.py"
    source.write_text("def load_release_model(path, **kwargs):\n    return 'model', 'processor'\n")
    before = source.read_bytes()
    reference, model, processor = clef_runner.load(tmp_path, device="cpu")
    assert (model, processor) == ("model", "processor")
    assert reference.__file__ == str(source) and source.read_bytes() == before
    assert not (tmp_path / "__pycache__").exists()
