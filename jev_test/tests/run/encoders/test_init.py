"""무엇: 인코더 등록과 선택 · 입력: ModelConfig · 출력: 측정기/거부 · 계약 §8-1."""

from dataclasses import replace

import pytest

from jeveval.run import encoders
from jeveval.run.encoders.clef_encode_record import ClefEncodeRecord
from jeveval.run.encoders.hf_chat_template import HfChatTemplateNoThink
from jeveval.run.encoders.pplx_decision_messages import PplxDecisionMessages


def test_three_encoder_rules_registered():
    assert encoders.ENCODERS == {
        "hf_chat_template_no_think": HfChatTemplateNoThink,
        "clef_encode_record": ClefEncodeRecord,
        "pplx_decision_messages": PplxDecisionMessages,
    }


@pytest.mark.parametrize("encoder", [{}, {"rule": None}, {"rule": "unregistered"},
                                   {"rule": ""}, {"rule": []}])
def test_unknown_rule_rejected_before_loading(env, monkeypatch, encoder):
    def forbidden(cfg):
        pytest.fail("invalid rule reached a loader")
    for rule in encoders.ENCODERS:
        monkeypatch.setitem(encoders.ENCODERS, rule, forbidden)
    with pytest.raises(ValueError, match="^unknown encoder rule$"):
        encoders.measurer_for(replace(env.cfg, encoder=encoder))


@pytest.mark.parametrize("rule", sorted(encoders.ENCODERS))
def test_measurer_for_dispatches_selected_config(env, monkeypatch, rule):
    cfg = replace(env.cfg, encoder={"rule": rule})
    sentinel, calls = object(), []
    def load(value):
        calls.append(value)
        return sentinel
    monkeypatch.setitem(encoders.ENCODERS, rule, load)
    assert encoders.measurer_for(cfg) is sentinel
    assert calls == [cfg]
