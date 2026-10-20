"""무엇: 라벨 없는 KoSGD 요청 · 입력: prefix/catalog/task/options · 출력: Request · 계약 §8-7 판 5 보정 2 WP3."""

from copy import deepcopy

from jeveval.contract.render import render_state
from jeveval.types import Request
from jeveval.types.kosgd_requests import DialoguePrefix


def build(prefix: DialoguePrefix, catalog, task, options, *, model):
    """정답·frames·baseline 없이 동결 문구를 전송 객체로 투영한다."""
    if not prefix.dialogue or prefix.dialogue[-1][0] != "USER" or len(prefix.dialogue) != prefix.turn_index + 1:
        raise ValueError("invalid USER prefix")
    if task.set != "kosgd2" or task.variant != "full" or len(task.questions) != 13:
        raise ValueError("pilot requires kosgd2 full 13 questions")
    state = dict(dialogue=[dict(speaker=s, utterance=u) for s, u in prefix.dialogue], catalog=catalog)
    rendered = render_state(state, task.state)
    questions = {}
    for q in task.questions:
        if q.type == "choice" and q.options != "catalog_intents_plus_none":
            raise ValueError("unexpected pilot options")
        questions[q.id] = dict(type=q.type, instructions=q.instructions,
                               criteria=deepcopy(options if q.type == "choice" else q.criteria))
    return Request(model, rendered.state, questions)
