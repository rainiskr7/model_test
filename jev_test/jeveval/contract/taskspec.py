"""무엇: task 스키마 검사 · 입력: 읽은 dict · 출력: TaskSpec/오류 목록 · 계약 §1-1."""

from copy import deepcopy
import re

from jeveval.types import QuestionSpec, TaskSpec


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _required(data, names, path):
    return [f"{path}.{name}: required" for name in names if name not in data]


def _question_errors(question, path):
    if not isinstance(question, dict):
        return [f"{path}: expected object"]
    errors = _required(question, ("id", "role", "type", "instructions", "label"), path)
    qid = question.get("id")
    if not isinstance(qid, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", qid):
        errors.append(f"{path}.id: expected ASCII snake_case")
    if question.get("role") not in ("success", "diagnostic"):
        errors.append(f"{path}.role: expected success or diagnostic")
    kind = question.get("type")
    if kind not in ("noul", "choice"):
        errors.append(f"{path}.type: expected noul or choice; score is out of scope")
    for name in ("instructions", "label"):
        if not _text(question.get(name)):
            errors.append(f"{path}.{name}: expected nonempty string")
    if kind == "noul":
        criteria = question.get("criteria")
        if not isinstance(criteria, dict) or any(
            not _text(criteria.get(key)) for key in ("true", "false")
        ):
            errors.append(f"{path}.criteria: true and false must be nonempty strings")
    if kind == "choice" and not _text(question.get("options")):
        errors.append(f"{path}.options: expected list name or per_item")
    return errors


def _state_errors(state):
    if not isinstance(state, dict):
        return ["task.state: expected object"]
    errors = []
    if state.get("kind") not in ("json_string", "plain_text"):
        errors.append("task.state.kind: expected json_string or plain_text")
    if state.get("kind") == "json_string":
        keys = state.get("keys")
        if not isinstance(keys, list) or not keys or not all(map(_text, keys)):
            errors.append("task.state.keys: expected nonempty list of strings")
        elif len(set(keys)) != len(keys):
            errors.append("task.state.keys: duplicate keys")
        target = state.get("target_key")
        if not _text(target) or not isinstance(keys, list) or target not in keys:
            errors.append("task.state.target_key: required member of keys")
    if state.get("kind") == "plain_text" and "target_key" in state:
        errors.append("task.state.target_key: forbidden for plain_text")
    return errors


def _per_item_errors(per_item, static_ids):
    path = "task.per_item_questions"
    if per_item is None:
        return []
    if not isinstance(per_item, dict):
        return [f"{path}: expected object or null"]
    errors = _required(per_item, ("id_pattern", "role", "type",
                                  "instructions_template", "label"), path)
    pattern = per_item.get("id_pattern")
    valid_pattern = isinstance(pattern, str) and pattern.count("{k}") == 1
    if not valid_pattern:
        errors.append(f"{path}.id_pattern: expected exactly one {{k}}")
    question = dict(per_item, id=pattern.replace("{k}", "1") if valid_pattern else "",
                    instructions=per_item.get("instructions_template"))
    errors.extend(_question_errors(question, path))
    if valid_pattern:
        before, after = pattern.split("{k}")
        matcher = re.compile(re.escape(before) + r"[1-9][0-9]*" + re.escape(after))
        for qid in static_ids:
            if matcher.fullmatch(qid):
                errors.append(f"{path}.id_pattern: duplicate {qid}")
    return errors


def validate_taskspec(data: dict) -> TaskSpec | list[str]:
    """입력을 변경하지 않으며 잘못된 문서의 독립 오류들을 모아 반환한다."""
    if not isinstance(data, dict):
        return ["task: expected object"]
    names = ("set", "variant", "state", "questions", "per_item_questions", "group_key")
    errors = _required(data, names, "task")
    for name in ("set", "variant", "group_key"):
        if not _text(data.get(name)):
            errors.append(f"task.{name}: expected nonempty string")
    errors.extend(_state_errors(data.get("state")))
    per_item = data.get("per_item_questions")
    questions = data.get("questions")
    if not isinstance(questions, list):
        errors.append("task.questions: expected list")
        questions = []
    seen = set()
    for index, question in enumerate(questions):
        path = f"task.questions[{index}]"
        errors.extend(_question_errors(question, path))
        qid = question.get("id") if isinstance(question, dict) else None
        if isinstance(qid, str):
            if qid in seen:
                errors.append(f"{path}.id: duplicate {qid}")
            seen.add(qid)
    errors.extend(_per_item_errors(per_item, seen))
    success = any(isinstance(q, dict) and q.get("role") == "success" for q in questions)
    success |= isinstance(per_item, dict) and per_item.get("role") == "success"
    if not success:
        errors.append("task.questions: at least one success question required")
    if errors:
        return errors
    values = deepcopy({name: data[name] for name in names})
    values["questions"] = [_make_question(q) for q in questions]
    return TaskSpec(**values)


def _make_question(question):
    names = ("id", "role", "type", "instructions", "label")
    values = {name: question[name] for name in names}
    specific = "criteria" if question["type"] == "noul" else "options"
    values[specific] = deepcopy(question[specific])
    return QuestionSpec(**values)
