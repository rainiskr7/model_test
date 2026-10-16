"""Clef 참조 인코더: 검증된 파일 로딩과 잘림 전 길이·offset 경계."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from jeveval.io.hashes import sha256_file
from jeveval.run.encoders import measurer_for
from jeveval.run.encoders import clef_encode_record as encoder
from jeveval.types import LengthInfo, Rendered, Request


class CharacterTokenizer:
    def __call__(self, text, **kwargs):
        assert kwargs == {"add_special_tokens": False, "return_offsets_mapping": True}
        return {"input_ids": list(range(len(text))), "offset_mapping": [(i, i + 1) for i in range(len(text))]}


@pytest.fixture
def local(tmp_path, env, monkeypatch):
    path = tmp_path / "joint_schema_model.py"
    path.write_text("# synthetic reference\n")
    cfg = replace(env.cfg, encoder={"rule": "clef_encode_record"},
        tokenizer={"path": str(tmp_path), "files_sha256": {path.name: sha256_file(path)}})
    loads, calls = [], []
    def encode(tokenizer, body, **kwargs):
        calls.append((body, kwargs))
        count = min(len(body["state"]), kwargs.get("max_state_tokens", len(body["state"])))
        return SimpleNamespace(input_ids=list(range(3 + count)))
    reference = SimpleNamespace(render=lambda state: state, encode_record=encode)
    def source(file, name):
        loads.append((file, name))
        return reference
    monkeypatch.setattr(encoder, "source_module", source)
    monkeypatch.setattr(encoder, "load_offline", lambda directory: CharacterTokenizer())
    plan = replace(env.plan, request=Request("m", "한글ab", {"q": {"type": "noul"}}),
                   rendered=Rendered("한글ab", 2))
    return cfg, plan, loads, calls, reference


def test_verified_reference_and_untruncated_manual_length(local):
    cfg, plan, loads, calls, _ = local
    measurer = measurer_for(cfg)
    assert isinstance(measurer, encoder.ClefEncodeRecord)
    assert loads[0][0].name == "joint_schema_model.py"
    assert measurer.measure(plan) == LengthInfo(7, 2, 100, 3)
    assert [kwargs for _, kwargs in calls] == [
        {"max_length": encoder.UNBOUNDED, "processor": None},
        {"max_length": encoder.UNBOUNDED, "processor": None, "max_state_tokens": 0}]


def test_reference_file_must_be_in_verified_manifest(local, tmp_path):
    cfg, _, loads, _, _ = local
    token = tmp_path / "tokenizer.json"
    token.write_text("{}")
    cfg = replace(cfg, tokenizer={"path": str(tmp_path), "files_sha256": {token.name: sha256_file(token)}})
    with pytest.raises(ValueError, match="tokenizer.files_sha256 must list joint_schema_model.py"):
        measurer_for(cfg)
    assert loads == []


@pytest.mark.parametrize("change,message", [("kind", "requires a systemone request"),
    ("request", "requires a systemone request"), ("limit", "must not be null"),
    ("render", "rendering differs"), ("end", "target end must be inside state"),
    ("count", "state token count differs")])
def test_invalid_measurement_boundaries(local, change, message):
    cfg, plan, _, _, reference = local
    if change == "kind":
        plan = replace(plan, kind="b1")
    elif change == "request":
        plan = replace(plan, request=None)
    elif change == "limit":
        cfg = replace(cfg, limit={"tokens": None})
    elif change == "render":
        reference.render = lambda state: "different"
    elif change == "end":
        plan = replace(plan, rendered=Rendered("한글ab", True))
    elif change == "count":
        reference.encode_record = lambda *a, **k: SimpleNamespace(input_ids=[1])
    with pytest.raises(ValueError, match=message):
        measurer_for(cfg).measure(plan)


@pytest.mark.parametrize("offsets,count,message", [([(0, 1)], 2, "offset count differs"),
    ([(0, 5)], 1, "invalid token offsets"), ([(True, 1)], 1, "invalid token offsets"),
    ([(2, 1)], 1, "invalid token offsets")])
def test_invalid_token_offsets(offsets, count, message):
    with pytest.raises(ValueError, match=message):
        encoder._offsets({"offset_mapping": offsets}, "text", count)
