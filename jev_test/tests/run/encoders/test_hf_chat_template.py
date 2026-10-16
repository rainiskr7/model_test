"""무엇: 오프라인 B1 측정 검증 · 입력: tmp_path 합성 WordLevel/BPE · 출력: 길이·거부 · 계약 §4-3·§8-6."""

from dataclasses import replace
import json
import os

import pytest
from tokenizers import Tokenizer, models, pre_tokenizers
from transformers import AutoTokenizer, PreTrainedTokenizerFast

from jeveval.io.hashes import sha256_file
from jeveval.run.encoders import ENCODERS, measurer_for
from jeveval.run.encoders.hf_chat_template import HfChatTemplateNoThink
from jeveval.run.plan_calls import plan_calls
from jeveval.types import B1Call, LengthInfo, Rendered


TEMPLATE = ("{{ bos_token }} {% if enable_thinking %}think {% endif %}"
            "{% for m in messages %}{{ m.role }} {{ m.content }} {{ eos_token }} {% endfor %}"
            "{% if add_generation_prompt %}assistant {% endif %}")


@pytest.fixture
def local(tmp_path, env):
    """다운로드 없이 config와 tokenizer.json을 만들고 수동 계산 가능한 호출을 준다."""
    words = "[UNK] [BOS] [END] system user assistant quiet alpha beta tail ask think".split()
    backend = Tokenizer(models.WordLevel(dict(zip(words, range(len(words)))), unk_token="[UNK]"))
    backend.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=backend, unk_token="[UNK]",
        bos_token="[BOS]", eos_token="[END]", chat_template=TEMPLATE)
    tokenizer.save_pretrained(tmp_path)
    config = tmp_path / "tokenizer_config.json"
    data = json.loads(config.read_text())
    data["chat_template"] = TEMPLATE
    config.write_text(json.dumps(data))
    hashes = {p.name: sha256_file(p) for p in tmp_path.iterdir() if p.is_file()}
    (tmp_path / "unlisted.txt").write_text("ignored")
    cfg = replace(env.bcfg, encoder={"rule": "hf_chat_template_no_think"},
                  tokenizer={"path": str(tmp_path), "files_sha256": hashes})
    call = B1Call("q", [{"role": "system", "content": "quiet"},
        {"role": "user", "content": "alpha beta tail ask"}], ["A"], {"A": "true"}, {})
    plan = replace(env.plan, kind="b1", b1_call=call, rendered=Rendered("alpha beta tail", 10))
    return cfg, plan


def test_verified_load_and_manual_length(local, monkeypatch):
    """전체=11·state=3·대상=2·고정부=8을 독립 검산하고 로드 조건을 확인한다."""
    cfg, plan = local
    calls, original = [], AutoTokenizer.from_pretrained
    def load(path, **kwargs):
        """실제 로컬 로드에 위임하고 오프라인 인자를 기록한다."""
        calls.append((path, kwargs, os.environ["HF_HUB_OFFLINE"],
                      os.environ["TRANSFORMERS_OFFLINE"]))
        return original(path, **kwargs)
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", load)
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        monkeypatch.setenv(key, "0")
    measurer = measurer_for(cfg)
    assert ENCODERS[cfg.encoder["rule"]] is HfChatTemplateNoThink
    assert calls == [(cfg.tokenizer["path"],
                      {"local_files_only": True, "trust_remote_code": False}, "1", "1")]
    ids = measurer.tokenizer.apply_chat_template(plan.b1_call.messages,
        add_generation_prompt=True, enable_thinking=False, tokenize=True, return_dict=False)
    assert measurer.measure(plan) == LengthInfo(11, 2, 100, 8)
    assert len(ids) == 11


@pytest.mark.parametrize("case", ["missing", "mismatch", "empty", "null"])
def test_hash_failures_before_load(local, monkeypatch, case):
    """누락·다른 해시·미확정 목록은 토크나이저를 읽기 전에 거부한다."""
    cfg, _ = local
    hashes = dict(cfg.tokenizer["files_sha256"])
    if case == "missing":
        hashes["missing.json"] = "0" * 64
    elif case == "mismatch":
        hashes["tokenizer.json"] = "0" * 64
    else:
        hashes = {} if case == "empty" else None
    def unexpected(*args, **kwargs):
        """해시 검증 실패 뒤 로드 호출을 금지한다."""
        pytest.fail("loader called before hash verification")
    monkeypatch.setattr(AutoTokenizer, "from_pretrained", unexpected)
    with pytest.raises(ValueError):
        measurer_for(replace(cfg, tokenizer={**cfg.tokenizer, "files_sha256": hashes}))


@pytest.mark.parametrize("rule", [None, "unregistered"])
def test_unknown_rule(env, rule):
    """미등록 규칙은 파일 접근 없이 거부한다."""
    with pytest.raises(ValueError, match="rule"):
        measurer_for(replace(env.cfg, encoder={"rule": rule}))


def test_systemone_and_null_limit(local):
    """systemone은 미구현이며 B1의 null 상한은 측정 오류다."""
    cfg, plan = local
    measurer = measurer_for(replace(cfg, limit={"tokens": None}))
    with pytest.raises(NotImplementedError):
        measurer.measure(replace(plan, kind="systemone"))
    with pytest.raises(ValueError, match="limit"):
        measurer.measure(plan)


@pytest.mark.parametrize("value", [(1, 2), [[1]], [True], ["1"]])
def test_invalid_template_ids(local, monkeypatch, value):
    """list[int] 이외 반환을 거부한다."""
    cfg, plan = local
    measurer = measurer_for(cfg)
    monkeypatch.setattr(measurer.tokenizer, "apply_chat_template", lambda *a, **k: value)
    with pytest.raises(ValueError, match=r"list\[int\]"):
        measurer.measure(plan)


def test_reencoding_mismatch(local, monkeypatch):
    """문자 위치의 근거가 다른 ID 목록이면 측정을 거부한다."""
    cfg, plan = local
    measurer = measurer_for(cfg)
    original = measurer.tokenizer.apply_chat_template
    def altered(*args, **kwargs):
        """렌더 문자열은 그대로 두고 직접 얻은 ID만 바꾼다."""
        result = original(*args, **kwargs)
        return result + [0] if kwargs["tokenize"] else result
    monkeypatch.setattr(measurer.tokenizer, "apply_chat_template", altered)
    with pytest.raises(ValueError, match="re-encoded"):
        measurer.measure(plan)


@pytest.mark.parametrize("case", ["prefix", "duplicate", "absent", "users", "boundary"])
def test_invalid_state_location(local, case):
    """위치 불명·다중 user·음수 상대 offset은 추측으로 보정하지 않는다."""
    cfg, plan = local
    measurer = measurer_for(cfg)
    if case == "prefix":
        plan = replace(plan, rendered=Rendered("beta", 4))
    elif case == "duplicate":
        plan.b1_call.messages[0]["content"] = plan.b1_call.messages[1]["content"]
    elif case == "absent":
        measurer.tokenizer.chat_template = "system quiet assistant"
    elif case == "users":
        plan.b1_call.messages.append({"role": "user", "content": "ask"})
    else:
        measurer.tokenizer.chat_template = TEMPLATE.replace("{{ m.role }} ", "{{ m.role }}")
    with pytest.raises(ValueError):
        measurer.measure(plan)


@pytest.mark.parametrize("end,expected", [(0, 0), (3, 1), (5, 1), (10, 2), (15, 3)])
def test_target_boundaries(local, end, expected):
    """토큰 내부와 끝 경계의 대상 끝을 손으로 센 값과 비교한다."""
    cfg, plan = local
    plan = replace(plan, rendered=Rendered(plan.rendered.state, end))
    assert measurer_for(cfg).measure(plan) == LengthInfo(11, expected, 100, 8)


def test_real_call_plan_integration(local, env):
    """기존 B1 문구 생성부터 측정까지 연결하고 고정부를 확인한다."""
    cfg, _ = local
    item = replace(env.item, state_fields="alpha beta tail")
    plan = plan_calls(item, env.task, cfg, env.b1)[0]
    info = measurer_for(cfg).measure(plan)
    assert not plan.local_errors and info.target_end == 3
    assert info.fixed_tokens == info.length_tokens - 3


@pytest.mark.parametrize("end,expected", [(0, 0), (1, 3), (2, 6)])
def test_byte_level_bpe_state_offsets(tmp_path, env, end, expected):
    """실제 합성 byte-level BPE의 한국어 중복 offsets가 state 이동 뒤에도 보존된다."""
    alphabet = sorted(pre_tokenizers.ByteLevel.alphabet())
    backend = Tokenizer(models.BPE(dict(zip(alphabet, range(256))), merges=[]))
    backend.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False)
    template = ("{% for m in messages %}{{ m.content }}{% endfor %}"
                "{% if add_generation_prompt %}!{% endif %}")
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=backend, chat_template=template)
    tokenizer.save_pretrained(tmp_path)
    cfg = replace(env.bcfg, encoder={"rule": "hf_chat_template_no_think"},
        tokenizer={"path": str(tmp_path), "files_sha256": {
            p.name: sha256_file(p) for p in tmp_path.iterdir() if p.is_file()}})
    call = B1Call("q", [{"role": "system", "content": "!"},
        {"role": "user", "content": "한글?"}], ["A"], {"A": "true"}, {})
    plan = replace(env.plan, kind="b1", b1_call=call, rendered=Rendered("한글", end))
    measurer = measurer_for(cfg)
    encoded = measurer.tokenizer("!한글?!", add_special_tokens=False, return_offsets_mapping=True)
    assert encoded["offset_mapping"] == [(0, 1)] + [(1, 2)] * 3 + [(2, 3)] * 3 + [(3, 4), (4, 5)]
    assert measurer.measure(plan) == LengthInfo(9, expected, 100, 3)
