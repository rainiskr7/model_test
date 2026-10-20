"""무엇: 모집단 합성 입력 · 입력: 질문/예측 · 출력: Item/final/outcome · 계약 §7-6 시험."""

import json
from pathlib import Path

from jeveval.score.tasks import outcome
from jeveval.score.set_metrics import metric_spec
from jeveval.types import BoundQuestion, CallRecord, FinalRecord, Item, ParsedAnswer


def fixture(name):
    return json.loads((Path(__file__).parents[1] / "fixtures/scoring" / name).read_text())


def question(qid, gold="true", label="synthetic", options=None, role="success"):
    return BoundQuestion(qid, role, "choice" if options else "noul", "synthetic",
                         options, None, label, gold)


def answer(value="true", probs=None, confidence=.9):
    return ParsedAnswer("choice" if probs else "noul", value,
                        probs if probs is not None else {"true": .9, "false": .1}, confidence)


def record(questions, answers, *, set_name="synthetic", gid="g", iid="i", stage="test",
           status="ok", baseline=None, flags=()):
    item = Item(set_name, gid, iid, "synthetic", questions,
                dict(service=None, stratum=None, flags=list(flags)), baseline)
    lid = f"{set_name}:{gid}:{iid}"
    call = CallRecord(lid, 1, status, None, ["choice_not_argmax"], "a" * 64, None, None, answers)
    final = FinalRecord(lid, status, None, False, ["choice_not_argmax"], [call])
    return item, final, outcome(final, item, stage)


def population_args(records, set_name="synthetic", certified=True, unit="group_representative"):
    return dict(items={f.logical_id: i for i, f, _ in records},
                finals=[f for _, f, _ in records], outcomes=[r for _, _, r in records],
                set_name=set_name, certified=certified, unit=unit, spec=metric_spec(set_name))
