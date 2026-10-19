"""무엇: 칸/행동 오류 분해 손계산 · 입력: 각 오류와 순서 반례 · 출력: 분할·그리드 · 계약 §7-6."""

import pytest

from jeveval.score.kosgd_decompose import decompose
from tests.score.population_support import answer, question, record


def example(gold, predicted, gid="g", act=False):
    options = {v: v for v in ("A", "B", "C", "NONE")}
    qs = [question("one", gold[0], "ongoing_slot_1", options),
          question("two", gold[1], "ongoing_slot_2", options), question("act", "true")]
    answers = {"one": answer(predicted[0], {predicted[0]: 1}),
               "two": answer(predicted[1], {predicted[1]: 1}), "act": answer("false" if act else "true")}
    item, final, _ = record(qs, answers, gid=gid)
    return item, final


def test_mutually_exclusive_priority_grid_and_unique_gold_duplicate_match():
    cases = [(["A", "NONE"], ["A", "A"], False), (["A", "NONE"], ["B", "NONE"], True),
             (["A", "NONE"], ["A", "B"], False), (["A", "B"], ["A", "NONE"], False),
             (["A", "B"], ["C", "NONE"], False), (["A", "B"], ["B", "A"], False),
             (["NONE", "NONE"], ["NONE", "NONE"], True)]
    examples = [example(g, p, str(i), act) for i, (g, p, act) in enumerate(cases)]
    d = decompose([f for _, f in examples], {f.logical_id: i for i, f in examples}, "test")
    assert (d.correct, d.slots_only, d.actions_only, d.both) == (1, 4, 1, 1)
    assert d.errors == dict(duplicate=1, replacement=1, addition=1, omission=1, other=1)
    assert d.duplicate_unique_match == 1 and d.grid[1][2] == 2
    assert sum(map(sum, d.grid)) == 7


def test_partial_missing_rejected():
    with pytest.raises(ValueError):
        example(["A", None], ["A", "NONE"])
