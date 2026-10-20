"""무엇: 저장소 밖 참조 checkpoint · 입력: 로컬 절대/없는 경로 · 출력: 성공·비공개 경로 제거·거부 · 계약 H·I/T-h."""

from pathlib import Path

import pytest

from jeveval.io.hashes import sha256_file
from jeveval.io.run_files import read_json
from jeveval.run import cmd_t0
from . import fakes
from .support import inputs, stage


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


@pytest.mark.parametrize("family", ["clef", "clef_flash", "pplx_v1", "pplx_v1_1"])
def test_external_absolute_checkpoint_and_private_fingerprint(setup, tmp_path, monkeypatch, family):
    ctx = setup(family)
    inputs(ctx)
    username = "private_gpu_user_82491"
    checkpoint = tmp_path / "home" / username / "weights"
    checkpoint.mkdir(parents=True)
    weights = checkpoint / "model.fake"
    weights.write_bytes(b"external checkpoint distinct from repository checkpoint")
    assert checkpoint.is_absolute() and not checkpoint.is_relative_to(ctx.root)
    loader, loaded = cmd_t0.t0_runner.load, []
    def load(family, path, **kwargs):
        loaded.append(path)
        module = fakes.module()
        return loader(family, path, reference=module, answer_module=module, server=module, **kwargs)
    monkeypatch.setattr(cmd_t0.t0_runner, "load", load)
    result = stage(ctx, "reference", checkpoint=str(checkpoint), device="cpu")
    assert result["ok"] is True and result["cases"] == 2 and result["variants"] > 0
    assert loaded == [checkpoint.resolve()]
    path = ctx.directory / "fingerprint.json"
    fingerprint = read_json(path)
    assert fingerprint["reference"]["checkpoint_files"] == {"model.fake": sha256_file(weights)}
    text = path.read_text()
    assert str(checkpoint) not in text and str(tmp_path) not in text and username not in text
    assert not any(Path(value).is_absolute() for value in strings(fingerprint))


@pytest.mark.parametrize("absolute", [True, False], ids=["absolute_external", "relative_to_root"])
def test_missing_checkpoint_rejected_before_loading_or_writing(setup, tmp_path, monkeypatch, absolute):
    ctx = setup()
    inputs(ctx)
    checkpoint = tmp_path / "missing_weights" if absolute else Path("missing_weights")
    resolved = checkpoint if absolute else ctx.root / checkpoint
    assert not resolved.exists()
    before = (ctx.directory / "fingerprint.json").read_bytes()
    monkeypatch.setattr(cmd_t0.t0_runner, "load", lambda *a, **k: pytest.fail("missing checkpoint loaded"))
    with pytest.raises(ValueError, match="local checkpoint directory required"):
        stage(ctx, "reference", checkpoint=str(checkpoint), device="cpu")
    assert not (ctx.directory / "reference.jsonl").exists()
    assert not (ctx.directory / "variants.jsonl").exists()
    assert (ctx.directory / "fingerprint.json").read_bytes() == before
