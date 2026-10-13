"""무엇: 임계값·봉인 재계산 검증 · 입력: 기존 fixture·합성 분할 · 출력: 대조 · 계약 §7-5·§8-6 E."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from jeveval.score.tasks import outcome
from jeveval.score.threshold import RULE, TAUS, UNIT, dev_complete, select, threshold_file
from jeveval.types import BoundQuestion, FinalRecord, Item, RequestOutcome, SplitPlan, ThresholdFile


ROOT = Path(__file__).parents[1] / "fixtures"


def row(values, index=0, stage="dev"):
    return RequestOutcome(logical_id=f"synthetic:{index}:i", group_id=str(index), stage=stage,
                          status="ok" if values["valid"] else "error", valid=values["valid"],
                          mask_empty=values["mask_empty"], s=values["s"], wrong=values["wrong"],
                          gold={}, answer={} if values["valid"] else None,
                          length_max=None, meta={}, roles=values.get("roles", {}))


def build(dev, raw=b"synthetic"):
    return threshold_file(model="synthetic", set="synthetic", variant="full", run_id="r1",
                          dev_sha256=hashlib.sha256(raw).hexdigest(), dev_nbytes=len(raw), dev=dev)


def test_threshold_fixtures_and_test_variants():
    fixture = json.loads((ROOT / "scoring/threshold_cases.json").read_text())
    for case in fixture["cases"]:
        dev = [row(r, i) for i, r in enumerate(case["dev"])]
        before = deepcopy(dev)
        result = build(dev)
        assert result.to_dict()["by_tau"] == case["expected"]["by_tau"]
        for tau, expected in case["expected"]["by_tau"].items():
            assert select(dev, tau).to_dict() == expected
        for variant in case.get("test_variants", []):
            stages = {"dev": dev, "test": [row(r, i, "test") for i, r in enumerate(variant)]}
            assert build(stages["dev"]) == result
            with pytest.raises(ValueError, match="only dev"):
                build(stages["dev"] + stages["test"])
        assert dev == before
        assert ThresholdFile.from_dict(result.to_dict()) == result
        assert (result.schema, result.rule, result.unit) == ("threshold/1", RULE, UNIT)
        assert result.dev_input["n_groups"] == len(dev)
        assert result.dev_input["n_denom"] + result.dev_input["n_empty_mask"] == len(dev)


def test_seal_fixtures_through_tasks_and_threshold_file():
    fixture = json.loads((ROOT / "seal/cases.json").read_text())
    for case in fixture["cases"]:
        if case["threshold_raw"] is None:
            continue
        raw = case["dev_final_raw"].encode("utf-8")
        finals = [FinalRecord.from_dict(json.loads(line))
                  for line in raw.decode().splitlines() if line]
        dev = []
        for final in finals:
            set_name, group, item_id = final.logical_id.split(":")
            questions = [BoundQuestion(qid, "success", "noul", "synthetic", None,
                                       {"true": "yes", "false": "no"}, "synthetic", gold)
                         for qid, gold in case["gold"].items()]
            item = Item(set_name, group, item_id, "synthetic", questions,
                        {"service": None, "stratum": None, "flags": []}, None)
            dev.append(outcome(final, item, "dev"))
        actual = build(dev, raw)
        stored = ThresholdFile.from_dict(json.loads(case["threshold_raw"]))
        assert (actual.by_tau == stored.by_tau) == case["expected"]["checks"]["b"]
        assert actual.dev_input["sha256"] == hashlib.sha256(raw).hexdigest()
        assert actual.dev_input["nbytes"] == len(raw)


def test_dev_complete_compares_representatives_not_group_ids():
    plan = SplitPlan(set="synthetic", seed=1, pool_rule={}, allocation={},
                     groups={"g": ["1", "2"], "h": ["3"], "t": ["4"]},
                     representative={"g": "synthetic:g:2", "h": "synthetic:h:3", "t": "synthetic:t:4"},
                     dev=["g", "h"], test=["t"], diagnostic_demotions=[],
                     extra=["synthetic:g:1"], notes={})
    before = deepcopy(plan)
    assert dev_complete(["synthetic:h:3", "synthetic:g:2"], plan) == []
    assert dev_complete(["synthetic:g:2", "synthetic:g:2", "synthetic:g:1", "synthetic:t:4"], plan) == [
        "missing dev logical_id: synthetic:h:3",
        "unexpected dev logical_id: synthetic:g:1",
        "unexpected dev logical_id: synthetic:t:4",
        "duplicate dev logical_id: synthetic:g:2",
    ]
    assert len(dev_complete(["g", "h"], plan)) == 4
    assert dev_complete([], replace(plan, dev=[])) == []
    assert plan == before


@pytest.mark.parametrize("stage", ["test", "extra"])
def test_nondev_rejected_even_when_invalid_or_empty(stage):
    values = dict(valid=False, mask_empty=True, s=None, wrong=None)
    with pytest.raises(ValueError, match="only dev"):
        build([row(values, stage=stage)])


def test_empty_dev_counts_and_null_thresholds():
    result = build([], b"")
    assert result.dev_input == dict(path="dev/final.jsonl", sha256=hashlib.sha256(b"").hexdigest(),
                                    nbytes=0, n_groups=0, n_denom=0, n_empty_mask=0)
    assert tuple(result.by_tau) == TAUS
    for tau, threshold in result.by_tau.items():
        assert threshold.to_dict() == dict(tau=tau, status="NO_THRESHOLD", t_star=None,
                                          n_accepted=None, k_errors=None, coverage={"num": 0, "den": 0})


@pytest.mark.parametrize("tau,n_boundary", [("0.01", 200), ("0.02", 100), ("0.05", 40)])
def test_exact_risk_boundary_and_one_fewer_request(tau, n_boundary):
    dev = [row(dict(valid=True, mask_empty=False, s=.8, wrong=i == 0), i)
           for i in range(n_boundary)]
    assert select(dev, tau).n_accepted == n_boundary
    assert select(dev[:-1], tau).status == "NO_THRESHOLD"


def test_candidate_t_is_observed_score_and_input_order_independent():
    dev = [row(dict(valid=True, mask_empty=False, s=s, wrong=wrong), i)
           for i, (s, wrong) in enumerate([(.9, False), (.8, True), (.7, False)])]
    for tau in TAUS:
        # (.8, .9]은 같은 한 건을 수락하지만 후보는 관측 점수 .9뿐이다.
        assert select(dev, tau).t_star == .9
        assert select(list(reversed(dev)), tau) == select(dev, tau)
