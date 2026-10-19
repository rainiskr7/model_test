"""무엇: KLUE-MRC 항목 · 입력: 모든 guid 행·분할·task·목록 · 출력: 대표 Item · 계약 §6-2."""

from jeveval.data.items.common import assemble, fields, questions
from jeveval.types import Item, ItemFields, SourceRow, SplitPlan, TaskSpec


def build_items(rows: list[SourceRow], plan: SplitPlan, task: TaskSpec,
                lists: dict, rules: dict) -> dict[str, list[Item]]:
    """context·question state와 bool 정답, source 층을 보존한다."""
    def make(selected, bucket) -> ItemFields:
        row = selected[0].fields
        state = {key: row[key] for key in ("context", "question")}
        return fields(state, questions(selected, task, lists, rules=rules), stratum=row["source"])

    return assemble(rows, plan, task, make)
