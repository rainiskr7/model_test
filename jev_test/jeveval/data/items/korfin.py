"""무엇: KorFin SRC 항목 · 입력: SID 행·분할·task·목록 · 출력: aspect 질문 Item · 계약 §6-2."""

from jeveval.data.items.common import assemble, fields, questions
from jeveval.types import Item, ItemFields, SourceRow, SplitPlan, TaskSpec


def _bindings(rows):
    if not rows or any(type(row.fields.get("SRC")) is not str for row in rows):
        raise ValueError("invalid KorFin SRC")
    texts = {row.fields["SRC"] for row in rows}
    if len(texts) != 1:
        raise ValueError("KorFin item has different SRC values")
    aspects = [row.fields.get("ASPECT") for row in rows]
    if any(type(a) is not str for a in aspects) or len(set(aspects)) != len(aspects):
        raise ValueError("invalid or duplicate KorFin ASPECT")
    return [{"k": i, "ASPECT": aspect} for i, aspect in enumerate(aspects, 1)]


def build_items(rows: list[SourceRow], plan: SplitPlan, task: TaskSpec,
                lists: dict, rules: dict) -> dict[str, list[Item]]:
    """SRC의 SID 원본 순서대로 질문·정답을 연결하고 미포함 aspect를 표시한다."""
    def make(selected, bucket) -> ItemFields:
        bindings = _bindings(selected)
        text = selected[0].fields["SRC"]
        bound = questions(selected, task, lists, bindings=bindings, rules=rules)
        dynamic = bound[len(task.questions):]
        flags = ["aspect_not_in_text:" + q.id for b, q in zip(bindings, dynamic)
                 if b["ASPECT"] not in text]
        return fields(text, bound, flags=flags)

    return assemble(rows, plan, task, make)
