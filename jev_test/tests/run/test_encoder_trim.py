"""무엇: B1 trim 위치 보정 · 입력: 합성 byte-level BPE·공백 state · 출력: 길이·거부 · 계약 §4-3."""

from dataclasses import replace

import pytest
from tokenizers import Tokenizer, models, pre_tokenizers
from transformers import PreTrainedTokenizerFast

from jeveval.io.hashes import sha256_file
from jeveval.run.encoders import measurer_for
from jeveval.run.encoders.hf_chat_template import _state_span
from jeveval.run.plan_calls import plan_calls
from jeveval.types import B1Call, LengthInfo, Rendered


@pytest.fixture
def trimmed(tmp_path, env):
    """병합 없는 로컬 BPE와 실제 Jinja trim 템플릿을 만들어 읽는다."""
    alphabet = sorted(pre_tokenizers.ByteLevel.alphabet())
    backend = Tokenizer(models.BPE(dict(zip(alphabet, range(256))), merges=[]))
    backend.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False)
    template = ("{% for m in messages %}{{ m.content|trim }}{% endfor %}"
                "{% if add_generation_prompt %}!{% endif %}")
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=backend, chat_template=template)
    tokenizer.save_pretrained(tmp_path)
    cfg = replace(env.bcfg, encoder={"rule": "hf_chat_template_no_think"},
        tokenizer={"path": str(tmp_path), "files_sha256": {
            p.name: sha256_file(p) for p in tmp_path.iterdir() if p.is_file()}})
    return measurer_for(cfg)


def _plan(env, state, end, suffix="\n답: \t"):
    """state는 원문 그대로 보존하고 질문 뒤 공백도 trim하도록 합성한다."""
    call = B1Call("q", [{"role": "system", "content": "!"},
        {"role": "user", "content": state + suffix}], ["A"], {"A": "true"}, {})
    return replace(env.plan, kind="b1", b1_call=call, rendered=Rendered(state, end))


@pytest.mark.parametrize("prefix", ["", " ", "\t\n\u3000\u00a0"])
@pytest.mark.parametrize("end,expected", [(0, 0), (1, 3), (2, 6)])
def test_leading_trim_moves_state_and_target(trimmed, env, prefix, end, expected):
    """공백 종류·개수와 무관하게 한글의 마지막 바이트 조각 다음 번호를 얻는다."""
    plan = _plan(env, prefix + "한글", len(prefix) + end)
    text = trimmed.tokenizer.apply_chat_template(plan.b1_call.messages, tokenize=False,
        add_generation_prompt=True, enable_thinking=False, return_dict=False)
    assert text == "!한글\n답:!"
    assert _state_span(plan, text) == (1, 3, end)
    assert trimmed.measure(plan) == LengthInfo(13, expected, 100, 7)


def test_target_inside_removed_prefix_clamps_to_zero(trimmed, env):
    """대상 끝이 제거된 앞 공백 안에 있으면 음수 대신 0을 반환한다."""
    plan = _plan(env, " \t한글", 1)
    assert _state_span(plan, "!한글\n답:!") == (1, 3, 0)
    assert trimmed.measure(plan) == LengthInfo(13, 0, 100, 7)


def test_state_trailing_space_is_preserved_before_suffix(trimmed, env):
    """뒤쪽 trim은 답 접미사 뒤에만 적용하고 state 끝 공백 토큰을 보존한다."""
    plan = _plan(env, " 한글 ", 4)
    assert _state_span(plan, "!한글 \n답:!") == (1, 4, 3)
    assert trimmed.measure(plan) == LengthInfo(14, 7, 100, 7)


@pytest.mark.parametrize("state", ["", " ", "\t\n\u3000\u00a0"])
def test_all_whitespace_state_rejected(trimmed, env, state):
    """trim 뒤 state가 사라지는 경우는 위치를 추측하지 않고 거부한다."""
    with pytest.raises(ValueError, match="non-whitespace"):
        trimmed.measure(_plan(env, state, len(state)))


@pytest.mark.parametrize("state,suffix", [("한글", " \t"), (" 한글 ", "\t"),
                                           ("한글", "\n답: 한글 \t")])
def test_trailing_trim_guard(trimmed, env, state, suffix):
    """state로 끝나는 user와 state 공백까지 제거하는 뒤쪽 trim을 거부한다."""
    with pytest.raises(ValueError, match="suffix"):
        trimmed.measure(_plan(env, state, len(state), suffix))


@pytest.mark.parametrize("text", ["!다른 본문!", "!한글\n답:!한글\n답:!"])
def test_trimmed_user_must_occur_exactly_once(env, text):
    """trim 뒤 본문도 없거나 둘 이상이면 거부한다."""
    with pytest.raises(ValueError, match="exactly once"):
        _state_span(_plan(env, " 한글", 2), text)


@pytest.mark.parametrize("raw", [" \t한글", "한글 \n", " \n한글\u3000", " \t한 글\n다음 \n"])
def test_plain_text_render_leaves_no_encoder_prefix_to_remove(trimmed, env, raw):
    """실제 호출 계획은 같은 정규화 state를 보내고 Item 원문과 내부 공백은 보존한다."""
    item = replace(env.item, state_fields=raw)
    before = item.to_dict()
    systemone, = plan_calls(item, env.task, env.cfg, None)
    b1, = plan_calls(item, env.task, env.bcfg, env.b1)
    state = raw.strip()
    assert not systemone.local_errors and not b1.local_errors
    assert systemone.rendered == b1.rendered == Rendered(state, len(state))
    assert systemone.request.state == state
    user = b1.b1_call.messages[1]["content"]
    assert user.startswith(state + "\n")
    assert len(user) - len(user.lstrip()) == 0  # encoder의 removed 계산
    text = trimmed.tokenizer.apply_chat_template(b1.b1_call.messages, tokenize=False,
        add_generation_prompt=True, enable_thinking=False, return_dict=False)
    start = len(env.b1.system.strip())
    assert _state_span(b1, text) == (start, start + len(state), len(state))
    assert trimmed.measure(b1).target_end == len(state.encode("utf-8"))
    assert item.to_dict() == before and item.state_fields == raw
