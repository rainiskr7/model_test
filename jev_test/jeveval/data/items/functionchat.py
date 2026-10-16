"""무엇: FunctionChat 항목 · 입력: 행·분할·task·목록 · 출력: 대표/extra Item · 계약 §6-2."""

from copy import deepcopy

from jeveval.data.items.common import assemble, fields, questions
from jeveval.types import Item, SourceRow, SplitPlan, TaskSpec


S = "누락된 필수 정보가 여러가지이면, 각각을 모두 빠짐없이 구체적으로 요청하세요."


def _state_and_options(row, lists):
    messages = deepcopy(row.fields["input_messages"])
    if not messages or messages[0].get("role") != "system":
        raise ValueError("FunctionChat first message must be system")
    messages[0]["content"] = messages[0]["content"].replace(S + " " + S, S)
    if messages[0]["content"].count(S) >= 2:
        raise ValueError("FunctionChat repeated normalization sentence remains")
    tools, options = deepcopy(row.fields["input_tools"]), {}
    for tool in tools:
        name = tool["function"]["name"]
        if name in options or name == "NONE":
            raise ValueError("duplicate or reserved tool name")
        options[name] = tool["function"]["description"]
    none = lists["functionchat_none"]
    if set(none) != {"NONE"}:
        raise ValueError("functionchat_none must contain only NONE")
    options.update(none)
    return dict(input_messages=messages, input_tools=tools), options


def build_items(rows: list[SourceRow], plan: SplitPlan, task: TaskSpec,
                lists: dict, rules: dict) -> dict[str, list[Item]]:
    """정규화된 한 입력에서 state와 도구 선택지를 만들며 원본을 변경하지 않는다."""
    def make(selected, bucket):
        state, options = _state_and_options(selected[0], lists)
        return fields(state, questions(selected, task, lists, options, rules=rules))

    return assemble(rows, plan, task, make, allow_extra=True)
