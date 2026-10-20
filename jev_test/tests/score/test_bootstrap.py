"""무엇: paired 묶음 재표집 검증 · 입력: 합성 outcome/Observation · 출력: 점추정·CI · 계약 §7-7."""

from copy import deepcopy
from dataclasses import replace
import random

import pytest

from jeveval.score.bootstrap import coverage_diff, f1_diff
from jeveval.types import Observation
from tests.score.population_support import answer, question, record


def coverage_rows():
    row = record([question("q")], {"q": answer()})[2]
    rows = [replace(row, logical_id=f"i{n}", group_id=f"g{n}", status=status,
                    valid=status == "ok", s=.8 if status == "ok" else None)
            for n, status in enumerate(("ok", "error", "rejected", "truncated", "ok"))]
    rows[-1] = replace(rows[-1], mask_empty=True, wrong=None)
    return rows


def test_coverage_uses_all_test_representatives_and_fixed_thresholds():
    rows = coverage_rows()
    models = dict(z=rows, a=list(reversed(rows)))
    before = deepcopy(models)
    result = coverage_diff(models, dict(z=None, a=.8), seed=42, set_name="s")
    assert result["reps"] == 2000 and result["n_groups"] == 4
    assert result["pairs"][0]["models"] == ["a", "z"]
    assert result["pairs"][0]["estimate"] == .25
    assert result["pairs"][0]["n_defined"] == 2000
    assert result == coverage_diff(dict(a=rows, z=list(reversed(rows))), dict(a=.8, z=None), seed=42, set_name="s")
    assert models == before
    equal = coverage_diff(models, dict(a=.8, z=.8), seed=42, set_name="s", reps=20)
    assert equal["pairs"][0]["ci95"] == [0, 0]


@pytest.mark.parametrize("defect", ["stage", "duplicate_group", "ids", "mask", "group", "threshold"])
def test_coverage_rejects_incomparable_inputs(defect):
    rows = coverage_rows()
    changed = list(rows)
    thresholds = dict(a=.5, b=.5)
    if defect == "stage":
        changed[0] = replace(changed[0], stage="extra")
    elif defect == "duplicate_group":
        changed[1] = replace(changed[1], group_id=changed[0].group_id)
    elif defect == "ids":
        changed.pop()
    elif defect == "mask":
        changed[0] = replace(changed[0], mask_empty=True)
    elif defect == "group":
        changed[0] = replace(changed[0], group_id="other")
    else:
        thresholds.pop("b")
    with pytest.raises(ValueError):
        coverage_diff(dict(a=rows, b=changed), thresholds, seed=1, set_name="s")


def test_f1_group_draws_keep_all_rows_and_pooled_aspects(monkeypatch):
    # g1: 두 행, 그중 i1의 aspect 두 개. g2: 한 행 한 aspect.
    rows = [Observation("i1", "g1", "aspect", "a", "a"),
            Observation("i1", "g1", "aspect", "a", "b"),
            Observation("i2", "g1", "aspect", "b", "b"),
            Observation("i3", "g2", "aspect", "b", "a")]
    other = [replace(o, answer=o.gold) for o in rows]
    # cohort 밖 및 다른 질문은 관측 통계에 들어가면 안 된다.
    ignored = [Observation("outside", "g3", "aspect", "b", "a"),
               Observation("i1", "g1", "other", "b", "a")]
    samples = iter([["g1", "g1"], ["g2", "g2"], ["g2", "g1"]])

    def choices(self, population, k):
        assert population == ["g1", "g2"] and k == 2
        return next(samples)

    monkeypatch.setattr(random.Random, "choices", choices)
    result = f1_diff(dict(a=rows + ignored, b=other), ["i1", "i2", "i3"],
                     seed=9, set_name="korfin_asc", question_id="aspect", reps=3)
    cell = result["pairs"][0]
    # a의 전체 F1=.5, g1만 F1=2/3, g2만 F1=0; b는 항상 1.
    assert cell["estimate"] == -.5
    assert cell["ci95"] == pytest.approx([-.975, -(.5 * .05 + (1 / 3) * .95)])
    assert cell["n_defined"] == 3


def test_functionchat_f1_is_clustered_and_deterministic_for_all_rows():
    rows = [Observation("dev", "g1", "action", "call", "call"),
            Observation("extra", "g1", "action", "slot", "call"),
            Observation("test", "g2", "action", "slot", "slot")]
    models = dict(z=rows, a=[replace(o, answer=o.gold) for o in rows])
    before = deepcopy(models)
    cohort = ["dev", "extra", "test"]
    result = f1_diff(models, cohort, seed=12, set_name="fc_call_decision", question_id="action", reps=50)
    assert result["n_groups"] == 2
    assert result["pairs"][0]["estimate"] == pytest.approx(1 / 3)
    reversed_models = {m: list(reversed(models[m])) for m in reversed(models)}
    assert result == f1_diff(reversed_models, list(reversed(cohort)), seed=12,
                             set_name="fc_call_decision", question_id="action", reps=50)
    assert models == before
    test = f1_diff(models, ["test"], seed=12, set_name="fc_call_decision", question_id="action", reps=10)
    assert test["n_groups"] == 1 and test["pairs"][0]["ci95"] == [0, 0]


@pytest.mark.parametrize("defect", ["gold", "group", "multiplicity"])
def test_f1_rejects_unpaired_gold_or_group(defect):
    row = Observation("i", "g", "q", "a", "a")
    changed = [replace(row, gold="b")] if defect == "gold" else [row]
    if defect == "group":
        changed = [replace(row, group_id="h")]
    if defect == "multiplicity":
        changed *= 2
    with pytest.raises(ValueError):
        f1_diff(dict(a=[row], b=changed), ["i"], seed=1, set_name="s", question_id="q")


def test_empty_metrics_are_null_and_tool_f1_is_rejected():
    result = f1_diff(dict(a=[], b=[]), [], seed=1, set_name="s", question_id="q", reps=2)
    assert result["pairs"] == [dict(models=["a", "b"], estimate=None, ci95=None, n_defined=0)]
    result = coverage_diff(dict(a=[], b=[]), dict(a=None, b=.5), seed=1, set_name="s", reps=2)
    assert result["pairs"][0]["estimate"] is None and result["pairs"][0]["ci95"] is None
    with pytest.raises(ValueError, match="tool"):
        f1_diff(dict(a=[], b=[]), [], seed=1, set_name="fc_call_decision", question_id="tool", f1_defined=False)
    obs = Observation("i", "g", "q", "a", "a")
    assert Observation.from_dict(obs.to_dict()) == obs
