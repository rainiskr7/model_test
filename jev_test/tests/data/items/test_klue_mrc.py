"""무엇: KLUE 항목 검사 · 입력: 합성 guid 행 · 출력: state·층·정답 · 계약 §6-2."""

from copy import deepcopy

from jeveval.data.items.common import summarize
from jeveval.data.items.klue_mrc import build_items
from jeveval.types import SourceRow


def test_state_stratum_answerable_and_stage_summary(settings, plan_for, label_rules):
    task, lists = settings("klue_mrc_answerable")
    rows = [SourceRow(task.set, guid, dict(guid=guid, context=context, question="q",
             source=source, is_impossible=value)) for guid, context, source, value in
            [("b", "ctx-b", "wiki", True), ("a", "ctx-a", "news", False)]]
    before = deepcopy(rows)
    result = build_items(rows, plan_for(rows, task), task, lists, label_rules)
    dev, test = result["dev"][0], result["test"][0]
    assert dev.state_fields == dict(context="ctx-a", question="q")
    assert dev.questions[0].gold == "true" and test.questions[0].gold == "false"
    assert dev.meta == dict(service=None, stratum="news", flags=[]) and dev.baseline is None
    assert summarize(result)["test"]["stratum"] == {"wiki": 1}
    assert summarize(result)["extra"] == dict(n=0, questions={}, flags={}, stratum=None, baseline=0)
    dev.state_fields.clear()
    assert rows == before
