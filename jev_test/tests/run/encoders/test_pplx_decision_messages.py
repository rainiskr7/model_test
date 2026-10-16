"""합성 WordLevel·가벼운 autojev 사본으로 PPLX 행별 길이와 usage 합을 검증한다."""

from dataclasses import replace
import json
import sys
from types import ModuleType, SimpleNamespace

import pytest
from tokenizers import Tokenizer, models, pre_tokenizers
from transformers import PreTrainedTokenizerFast

from jeveval.io.hashes import sha256_file
from jeveval.run.encoders import measurer_for
from jeveval.types import LengthInfo, Rendered, Request

TEMPLATE = ("{% if enable_thinking %}think {% endif %}"
    "{% for m in messages %}{{ m.role }} {{ m.content }} [END] {% endfor %}"
    "{% if add_generation_prompt %}assistant{% endif %}")
SOURCE = r'''from .types import describe

def decision_messages(row, codes):
    return [{"role": "system", "content": "choose " + " ".join(codes)},
            {"role": "user", "content": "State:\n" + describe(row["state"]) + "\n\nQuestion:\n" + row["question"]["instructions"]}]
'''


@pytest.fixture
def local(tmp_path, env, monkeypatch):
    monkeypatch.setattr(sys, "path", list(sys.path))
    names = {"autojev", "autojev.model", "autojev.types"} | {
        key for key in sys.modules if key.startswith("autojev.")}
    for name in names:
        monkeypatch.setitem(sys.modules, name, sys.modules.get(name))
        monkeypatch.delitem(sys.modules, name)
    words = "[UNK] [END] system user assistant choose A B alpha beta tail ask more now think State: Question:".split()
    backend = Tokenizer(models.WordLevel(dict(zip(words, range(len(words)))), unk_token="[UNK]"))
    backend.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=backend, unk_token="[UNK]", chat_template=TEMPLATE)
    tokenizer.save_pretrained(tmp_path)
    folder = tmp_path / "source/src/autojev"
    folder.mkdir(parents=True)
    (folder / "__init__.py").write_text("")
    (folder / "types.py").write_text("def describe(value):\n    return value if isinstance(value, str) else str(value)\n")
    (folder / "model.py").write_text(SOURCE)
    (tmp_path / "decision_config.json").write_text(json.dumps({"codes": ["A", "B"]}))
    manifest = {p.relative_to(tmp_path).as_posix(): sha256_file(p) for p in tmp_path.rglob("*") if p.is_file()}
    cfg = replace(env.cfg, encoder={"rule": "pplx_decision_messages"},
        tokenizer={"path": str(tmp_path), "files_sha256": manifest})
    questions = {"short": {"type": "noul", "instructions": "ask"},
                 "long": {"type": "noul", "instructions": "ask more now"}}
    plan = replace(env.plan, request=Request("m", "alpha beta tail", questions),
        question_ids=list(questions), question_types={key: "noul" for key in questions},
        rendered=Rendered("alpha beta tail", 10))
    return cfg, plan


def test_manual_row_max_fixed_target_and_usage_sum(local, monkeypatch):
    cfg, plan = local
    measurer = measurer_for(cfg)
    original, calls = measurer.tokenizer.apply_chat_template, []
    def render(messages, **kwargs):
        calls.append(kwargs)
        return original(messages, **kwargs)
    monkeypatch.setattr(measurer.tokenizer, "apply_chat_template", render)
    # short: system choose A B END user State: alpha beta tail Question: ask END assistant = 14.
    # long adds more/now: 16; state=3, target alpha/beta=2, usage=14+16.
    assert measurer.measure(plan) == LengthInfo(16, 2, 100, 13, usage_tokens=30)
    assert calls == [dict(tokenize=False, add_generation_prompt=True, enable_thinking=False),
        dict(tokenize=True, return_dict=False, add_generation_prompt=True, enable_thinking=False)] * 2


@pytest.mark.parametrize("name", ["decision_config.json", "source/src/autojev/model.py", "source/src/autojev/types.py"])
def test_required_manifest_files_rejected_before_loading(local, monkeypatch, name):
    from jeveval.run.encoders import pplx_decision_messages as encoder
    cfg, _ = local
    hashes = dict(cfg.tokenizer["files_sha256"])
    del hashes[name]
    def forbidden(*args):
        pytest.fail("missing manifest entry reached tokenizer load")
    monkeypatch.setattr(encoder, "load_offline", forbidden)
    with pytest.raises(ValueError) as error:
        measurer_for(replace(cfg, tokenizer={**cfg.tokenizer, "files_sha256": hashes}))
    assert str(error.value) == f"tokenizer.files_sha256 must list {name}"


def test_other_autojev_location_is_rejected(local, tmp_path, monkeypatch):
    cfg, _ = local
    other = ModuleType("autojev.model")
    other.__file__ = str(tmp_path / "other/model.py")
    monkeypatch.setitem(sys.modules, "autojev.model", other)
    with pytest.raises(ValueError, match=r"^autojev.model is already imported from a different location$"):
        measurer_for(cfg)
    assert sys.modules["autojev.model"] is other


def test_repeated_state_in_question_is_measured(local):
    cfg, plan = local
    questions = {"q": {"type": "noul", "instructions": plan.rendered.state}}
    plan = replace(plan, request=replace(plan.request, questions=questions))
    assert measurer_for(cfg).measure(plan) == LengthInfo(16, 2, 100, 13, usage_tokens=16)


def test_duplicate_state_blocks_are_rejected(local):
    cfg, plan = local
    marker = "State:\n" + plan.rendered.state + "\n\nQuestion:\n"
    questions = {"q": {"type": "noul", "instructions": marker + "ask"}}
    plan = replace(plan, request=replace(plan.request, questions=questions))
    with pytest.raises(ValueError, match="^rendered row must contain the State block exactly once$"):
        measurer_for(cfg).measure(plan)


def test_reencoded_token_ids_must_match(local, monkeypatch):
    cfg, plan = local
    measurer = measurer_for(cfg)
    original = measurer.tokenizer.apply_chat_template
    def altered(*args, **kwargs):
        result = original(*args, **kwargs)
        return result + [0] if kwargs["tokenize"] else result
    monkeypatch.setattr(measurer.tokenizer, "apply_chat_template", altered)
    with pytest.raises(ValueError, match="^re-encoded token IDs differ from chat template$"):
        measurer.measure(plan)


@pytest.mark.parametrize("media", ["images", "videos"])
def test_media_requests_are_not_supported(local, media):
    cfg, plan = local
    body = {**plan.request.to_dict(), media: ["synthetic-media"]}
    plan = replace(plan, request=SimpleNamespace(to_dict=lambda: body))
    with pytest.raises(NotImplementedError, match="^media requests are out of scope$"):
        measurer_for(cfg).measure(plan)


def test_b1_kind_is_rejected(local):
    cfg, plan = local
    with pytest.raises(ValueError, match="^pplx encoder requires a systemone request$"):
        measurer_for(cfg).measure(replace(plan, kind="b1"))


@pytest.mark.parametrize("source", ["describe", "rendered"])
def test_reference_state_must_match_rendered_state(local, monkeypatch, source):
    cfg, plan = local
    measurer = measurer_for(cfg)
    if source == "describe":
        monkeypatch.setattr(measurer.reference, "describe", lambda state: "changed")
    else:
        plan = replace(plan, rendered=Rendered("different", 1))
    with pytest.raises(ValueError, match="^reference state rendering differs from request$"):
        measurer.measure(plan)
