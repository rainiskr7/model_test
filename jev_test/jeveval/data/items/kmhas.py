"""무엇: K-MHaS 항목 · 입력: 행·분할·task·목록 · 출력: 대표 Item · 계약 §6-2."""

from jeveval.data.items.common import assemble, conflict_flags, fields, questions
from jeveval.types import Item, ItemFields, SourceRow, SplitPlan, TaskSpec


def build_items(rows: list[SourceRow], plan: SplitPlan, task: TaskSpec,
                lists: dict, rules: dict) -> dict[str, list[Item]]:
    """대표 원문·이름 라벨 정답과 묶음 전체의 라벨 충돌 flag를 조립한다."""
    def make(selected, bucket) -> ItemFields:
        return fields(selected[0].fields["text"], questions(selected, task, lists, rules=rules),
                      flags=conflict_flags(bucket, "label"))

    return assemble(rows, plan, task, make)
