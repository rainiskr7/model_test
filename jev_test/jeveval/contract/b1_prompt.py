"""무엇: B1 프롬프트 구성 · 입력: 설정·렌더·질문·호출 ID · 출력: B1Call · 계약 §2-5."""

from copy import deepcopy
import re

from jeveval.types import B1Call, B1Config, BoundQuestion, Rendered


def check_user_template(template) -> list[str]:
    """세 자리만 정확히 한 번 허용하고 이스케이프된 중괄호는 문자로 둔다."""
    if not isinstance(template, str):
        return ["user_template: expected string"]
    names, errors = [], []
    for match in re.finditer(r"\{\{|\}\}|\{([^{}]*)\}|[{}]", template):
        token, name = match.group(), match.group(1)
        if token in ("{{", "}}"):
            continue
        if name not in ("state", "instructions", "options"):
            errors.append(f"user_template: invalid placeholder {token}")
        else:
            names.append(name)
    for name in ("state", "instructions", "options"):
        if names.count(name) != 1:
            errors.append(f"user_template: expected exactly one {{{name}}}")
    return errors


def build_b1_call(config: B1Config, rendered: Rendered, question: BoundQuestion,
                  call_qid: str) -> B1Call:
    """라벨 토큰 ID는 후속 client에서 채우며 문구·매개변수는 설정을 사용한다."""
    if question.type == "score":
        raise NotImplementedError("score is out of scope")
    if question.type == "noul":
        ids, descriptions = ["true", "false"], question.criteria
    elif question.type == "choice":
        ids, descriptions = sorted(question.options), question.options
    else:
        raise ValueError("expected noul or choice")
    if len(ids) > len(config.labels):
        raise ValueError("not enough B1 labels")
    labels = config.labels[:len(ids)]
    label_map = dict(zip(labels, ids))
    lines = [f"{label}. [{option}] {descriptions[option]}" for label, option in label_map.items()]
    errors = check_user_template(config.user_template)
    if errors:
        raise ValueError("; ".join(errors))
    user = config.user_template.format(state=rendered.state, instructions=question.instructions,
                                       options="\n".join(lines))
    messages = [{"role": "system", "content": config.system}, {"role": "user", "content": user}]
    params = deepcopy(config.params)
    params["top_logprobs"] = len(ids)
    return B1Call(call_qid, messages, labels, label_map, params)
