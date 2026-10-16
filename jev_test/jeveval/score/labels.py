"""무엇: 정답 등록 규칙 · 입력: LabelVocab(어휘)·SourceRow·binding·options · 출력: 클래스 ID · 계약 §6-2."""

from functools import partial
from typing import Callable

from jeveval.score.kosgd_slots import fixed_gold
from jeveval.types import LabelVocab

CLOSE = ("GOODBYE", "THANK_YOU")


def _field(obj, key, kind):
    """필수 정답 필드 누락·null·타입 오류는 MISSING으로 바꾸지 않는다."""
    if not isinstance(obj, dict) or key not in obj or type(obj[key]) is not kind:
        raise ValueError(f"invalid or missing label field: {key}")
    return obj[key]


def _one(rows):
    """행 단위 규칙은 대상 SourceRow 하나만 받는다."""
    if len(rows) != 1:
        raise ValueError("label rule requires one row")
    return rows[0].fields


def _truth(value):
    return "true" if value else "false"


def _act(target, allowed, rows, binding, options):
    acts = set()
    for frame in _field(_one(rows), "frames", list):
        for action in _field(frame, "actions", list):
            acts.add(_field(action, "act", str))
    if not acts <= set(allowed):
        raise ValueError("unknown KoSGD act")
    targets = set(CLOSE) if target == "CLOSE" else {target}
    return _truth(bool(acts & targets))


def _slot(index, rows, binding, options):
    if not isinstance(options, dict):
        raise ValueError("slots require ordered options")
    intents = []
    for frame in _field(_one(rows), "frames", list):
        intent = _field(_field(frame, "state", dict), "active_intent", str)
        service = _field(frame, "service", str)
        if intent != "NONE":
            intents.append(service + "/" + intent)
    unique = list(dict.fromkeys(intents))
    return fixed_gold(unique, [key for key in options if key != "NONE"])[index]


def _fc_action(rows, binding, options):
    action = _field(_one(rows), "type_of_output", str)
    if action not in ("call", "slot", "relevance"):
        raise ValueError("unknown FunctionChat type_of_output")
    return action


def _fc_tool(rows, binding, options):
    action = _fc_action(rows, binding, options)
    truth = _field(_one(rows), "ground_truth", dict)
    if action != "call":
        if "tool_calls" in truth:
            raise ValueError("non-call row has tool_calls")
        return "NONE"
    calls = _field(truth, "tool_calls", list)
    if len(calls) != 1:
        raise ValueError("call row requires exactly one tool call")
    name = _field(_field(calls[0], "function", dict), "name", str)
    if not isinstance(options, dict) or name not in options:
        raise ValueError("gold tool outside options")
    return name


def _membership(field, target, rows, binding, options):
    labels = _field(_one(rows), field, list)
    if not all(type(name) is str for name in labels):
        raise ValueError("label names must be strings")
    return _truth(target in labels)


def _sentiment(rows, binding, options):
    aspect = _field(binding, "ASPECT", str)
    matches = [row for row in rows if _field(row.fields, "ASPECT", str) == aspect]
    if len(matches) != 1:
        raise ValueError("aspect must match exactly one row")
    return _field(matches[0].fields, "SENTIMENT", str)


def _answerable(rows, binding, options):
    return _truth(not _field(_one(rows), "is_impossible", bool))


def rules(vocab: LabelVocab) -> dict[str, Callable]:
    """어휘(configs/datasets.yaml label_vocab)로 전체 이름 등록표를 만든다. 규칙 본문은 코드, 어휘는 yaml."""
    acts = tuple(vocab.kosgd_acts)
    return {
        **{"act:" + act: partial(_act, act, acts) for act in acts if act not in CLOSE},
        "act:CLOSE": partial(_act, "CLOSE", acts),
        "ongoing_slot_1": partial(_slot, 0), "ongoing_slot_2": partial(_slot, 1),
        "fc:type_of_output": _fc_action, "fc:tool": _fc_tool,
        **{"kmhas:" + name: partial(_membership, "label_names", name) for name in vocab.kmhas},
        **{"kote:" + name: partial(_membership, "labels_majority", name) for name in vocab.kote},
        "korfin:sentiment": _sentiment, "klue:answerable": _answerable,
    }


def gold(label, rows, binding, options, rules: dict[str, Callable]) -> str | None:
    """등록표에서 전체 이름으로 규칙을 찾고 누락·잘못된 정답은 ValueError로 멈춘다."""
    if label not in rules:
        raise ValueError(f"unknown label rule: {label}")
    try:
        result = rules[label](rows, binding, options)
    except (KeyError, TypeError, AttributeError, IndexError) as exc:
        raise ValueError(f"invalid label input: {label}") from exc
    if type(result) is not str:
        raise ValueError(f"label rule returned a non-string: {label}")
    return result
