"""무엇: KOTE 항목 · 입력: 과반수 행·분할·task·목록 · 출력: 강등 반영 Item · 계약 §6-2."""

from dataclasses import replace

from jeveval.data.items.common import assemble, conflict_flags, fields, questions
from jeveval.types import Item, SourceRow, SplitPlan, TaskSpec


def build_items(rows: list[SourceRow], plan: SplitPlan, task: TaskSpec,
                lists: dict) -> dict[str, list[Item]]:
    """투표 과반수 정답을 쓰며 동결된 감정만 diagnostic으로 강등한다."""
    demotions = {"kote:" + name for name in plan.diagnostic_demotions}
    if not demotions <= {q.label for q in task.questions}:
        raise ValueError("demotion emotion has no question")

    def make(selected, bucket):
        bound = [replace(q, role="diagnostic") if q.label in demotions else q
                 for q in questions(selected, task, lists)]
        return fields(selected[0].fields["text"], bound,
                      flags=conflict_flags(bucket, "labels_majority"))

    return assemble(rows, plan, task, make)
