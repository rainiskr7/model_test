"""무엇: 항목 합성 준비 · 입력: 동결 task/합성 행 · 출력: 설정·합성 plan · 계약 §6-2."""

from pathlib import Path

import pytest

from jeveval.data.grouping import group_rows
from jeveval.io.config import load_taskspec
from jeveval.io.tasks import read_lists
from jeveval.types import SplitPlan


@pytest.fixture
def settings():
    root = Path(__file__).resolve().parents[3] / "configs/tasks"
    lists = read_lists(root / "lists")
    return lambda name: (load_taskspec(root / f"{name}.yaml"), lists)


@pytest.fixture
def plan_for():
    def make(rows, task, representatives=None, dev=None, extra=(), demotions=()):
        groups = group_rows(rows, task.group_key).members
        reps = {g: f"{task.set}:{g}:{members[0]}" for g, members in groups.items()}
        reps.update(representatives or {})
        ids = sorted(groups)
        dev = ids[:1] if dev is None else dev
        return SplitPlan(task.set, 1, {}, {}, groups, reps, dev,
                         [g for g in ids if g not in dev], list(demotions), list(extra), {})
    return make
