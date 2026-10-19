"""무엇: 위험 fixture·임계값 경계 · 입력: 기존 합성 fixture · 출력: 실제 RiskCell 대조 · 계약 §7-4."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from jeveval.io.run_files import json_bytes
from jeveval.score.risk import b_flip, n_min, risk_cell, risk_file, upper
from jeveval.score.threshold import TAUS, select
from jeveval.types import Item, RequestOutcome, RiskCell, Threshold


ROOT = Path(__file__).parents[1] / "fixtures/scoring"


def row(index, stage="dev", **values):
    data = dict(logical_id=f"synthetic:{index}:i", group_id=str(index), stage=stage,
                status="ok", valid=True, mask_empty=False, s=.9, wrong=False,
                gold={}, answer={}, length_max=12, meta={}, roles={})
    data.update(values)
    return RequestOutcome(**data)


def items(rows):
    return {r.logical_id: Item("synthetic", r.group_id, "i", "", [], {}, None) for r in rows}


def test_upper_and_minimum_fixtures():
    fixture = json.loads((ROOT / "risk_cases.json").read_text())
    for case in fixture["upper_bounds"]:
        actual = upper(case["k"], case["n"])
        assert actual is None if case["U"] is None else actual == pytest.approx(case["U"], abs=1e-9)
    for case in fixture["n_min"]:
        n, tau = n_min(case["tau"]), float(case["tau"])
        assert n == case["n"] and upper(0, n) <= tau < upper(0, n - 1)


def test_risk_fixture_statuses_counts_and_flip():
    for case in json.loads((ROOT / "risk_cases.json").read_text())["cases"]:
        expected, tau = case["expected"], case["tau"]
        dev = [row(i, s=.9 if i < 40 else .8, wrong=i >= 40) for i in range(50)]
        if expected["status"] == "NO_THRESHOLD":
            dev = [replace(r, wrong=True) for r in dev]
        n, k = expected["test"]["n_accepted"] or 0, expected["test"]["k_errors"] or 0
        test = [row(i, "test", s=.9 if i < n else .8, wrong=i < k)
                for i in range(expected["test"]["n_groups"])]
        result = risk_cell(tau=tau, threshold=select(dev, tau), dev=dev, test=test, test_items=items(test))
        actual = result.to_dict()
        # 기존 fixture는 세부 분포 입력이 없는 집계 예다. 채워진 인증 필드를 대조한다.
        for key in ("tau", "unit", "status", "insufficient_by_design", "t_star", "dev", "by_status"):
            assert actual[key] == expected[key]
        for key, value in expected["test"].items():
            assert actual["test"][key] == (pytest.approx(value, abs=1e-9) if key == "U" and value else value)
        assert RiskCell.from_dict(actual) == result
        if result.status == "MEETS":
            b = b_flip(k, n, tau)
            assert upper(k + b - 1, n) <= float(tau) < upper(k + b, n)
    assert b_flip(0, 600, "0.02") > 1


def test_threshold_fixtures_dev_blocks_and_immutable_test_threshold():
    for case in json.loads((ROOT / "threshold_cases.json").read_text())["cases"]:
        dev = [row(i, **{k: v for k, v in r.items() if k != "member_count"},
                   status="ok" if r["valid"] else "error") for i, r in enumerate(case["dev"])]
        before = deepcopy(dev)
        variants = case.get("test_variants", [[]])
        for tau in TAUS:
            threshold = select(dev, tau)
            assert threshold.to_dict() == case["expected"]["by_tau"][tau]
            for variant in variants:
                test = [row(i, "test", **r, status="ok" if r["valid"] else "error")
                        for i, r in enumerate(variant)]
                cell = risk_cell(tau=tau, threshold=threshold, dev=dev, test=test, test_items=items(test))
                assert cell.dev["n_groups"] == len(dev)
                assert cell.dev["n_denom"] == threshold.coverage["den"]
                assert cell.dev["n_accepted"] == threshold.n_accepted
                assert cell.dev["k_errors"] == threshold.k_errors
        assert dev == before


def test_risk_file_json_boundary_and_input_checks():
    dev, test = [row(0)], [row(1, "test")]
    cells = {tau: risk_cell(tau=tau, threshold=select(dev, tau), dev=dev,
                           test=test, test_items=items(test)) for tau in TAUS}
    args = dict(model="m", set="synthetic", variant="full", run_id="r", threshold_sha256="a" * 64)
    result = risk_file(**args, cells=cells)
    assert json.loads(json_bytes(result)) == result and result["schema"] == "risk/1"
    result["cells"]["0.01"]["test"]["n_groups"] = 99
    assert cells["0.01"].test["n_groups"] == 1
    with pytest.raises(ValueError, match="TAUS"):
        risk_file(**args, cells={})
    with pytest.raises(ValueError, match="representatives"):
        risk_cell(tau="0.02", threshold=select(dev, "0.02"), dev=dev,
                  test=test * 2, test_items=items(test))
    with pytest.raises(ValueError, match="tau/status"):
        risk_cell(tau="0.02", threshold=select(dev, "0.01"), dev=dev, test=[], test_items={})
    with pytest.raises(ValueError, match="counts"):
        risk_cell(tau="0.02", threshold=Threshold("0.02", "SELECTED", .9, 99, 0, {}),
                  dev=dev, test=[], test_items={})


@pytest.mark.parametrize("k,n", [(-1, 2), (3, 2), (True, 2), (0, -1)])
def test_upper_rejects_invalid_counts(k, n):
    with pytest.raises(ValueError):
        upper(k, n)


def test_question_and_request_share_unrounded_status_boundary():
    from jeveval.score.risk import cell_status, n_min, upper
    n = n_min("0.02")
    assert cell_status("0.02", None, None, None) == "NO_THRESHOLD"
    assert cell_status("0.02", .9, 0, None) == "UNDERPOWERED"
    assert cell_status("0.02", .9, n, upper(0, n)) == "MEETS"
    assert cell_status("0.02", .9, n, upper(1, n)) == "FAILS"
