"""무엇: 질문 펼치기 · 입력: TaskSpec·목록·binding·정답 함수 · 출력: BoundQuestion · 계약 §1-1·§6-2."""

from copy import deepcopy
import re

from jeveval.types import BoundQuestion


def _instructions(template, binding):
    """원래 틀의 토큰에만 replace를 적용하여 값 안의 중괄호는 재치환하지 않는다."""
    parts = re.split(r"(\{[^{}]+\})", template)
    for index in range(1, len(parts), 2):
        token = parts[index]
        name = token[1:-1]
        if name not in binding:
            raise ValueError(f"missing template binding: {name}")
        parts[index] = token.replace(token, str(binding[name]))
    return "".join(parts)


def _question(spec, binding, lists, item_options, gold_of):
    """선택지·criteria의 별칭을 끊고 정답의 클래스 소속을 검사한다."""
    options, criteria = None, None
    if spec["type"] == "choice":
        name = spec["options"]
        options = item_options if name == "per_item" else lists.get(name)
        if not isinstance(options, dict) or not options:
            raise ValueError(f"missing or invalid options: {name}")
        options = deepcopy(options)
    elif spec["type"] == "noul":
        criteria = deepcopy(spec["criteria"])
    else:
        raise ValueError("expected noul or choice")
    answer = gold_of(spec["label"], deepcopy(binding), deepcopy(options))
    if answer is not None and (type(answer) is not str or
                              answer not in (options if options is not None else ("true", "false"))):
        raise ValueError("gold outside question classes")
    return BoundQuestion(spec["id"], spec["role"], spec["type"], spec["instructions"],
                         options, criteria, spec["label"], answer)


def expand_questions(task, lists, item_options, bindings, gold_of) -> list[BoundQuestion]:
    """정적 질문 뒤 binding 순서로 확장하고 ID를 중복 없이 보존한다."""
    questions = [_question(q.to_dict(), {}, lists, item_options, gold_of) for q in task.questions]
    if task.per_item_questions is not None:
        for binding in bindings:
            spec = dict(task.per_item_questions)
            if type(binding.get("k")) is not int or binding["k"] < 1:
                raise ValueError("binding k must be a positive integer")
            spec["id"] = spec["id_pattern"].replace("{k}", str(binding["k"]))
            spec["instructions"] = _instructions(spec["instructions_template"], binding)
            questions.append(_question(spec, binding, lists, item_options, gold_of))
    seen = set()
    for question in questions:
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", question.id):
            raise ValueError("question ID must be ASCII snake_case")
        if question.id in seen:
            raise ValueError(f"duplicate question ID: {question.id}")
        seen.add(question.id)
    return questions
