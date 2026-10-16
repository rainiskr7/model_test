"""무엇: 결과 경로/요약 경계 · 입력: 식별자·RiskCell · 출력: 제한 경로·주 지표 · 계약 §5-1·§8-3."""

import pytest

from jeveval.run.layout import compare_dir, run_dir
from jeveval.run.summary import summary_from_risk


@pytest.mark.parametrize("bad", [".", "..", "_compare", "a/b", "/absolute", "a\\b", "", "a b"])
def test_invalid_identifiers(tmp_path, bad):
    for values in ((bad, "r1", "set", "full"), ("model", bad, "set", "full"),
                   ("model", "r1", bad, "full"), ("model", "r1", "set", bad)):
        with pytest.raises(ValueError):
            run_dir(tmp_path, *values)
    with pytest.raises(ValueError):
        compare_dir(tmp_path, bad, "set", "full")


def test_paths_and_symlink_escape(tmp_path):
    root = tmp_path / "results"
    root.mkdir()
    assert run_dir(root, "model", "r1", "set", "full") == root / "model/r1/A/set/full"
    assert compare_dir(root, "c1", "set", "full") == root / "_compare/c1/A/set/full"
    (root / "model").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        run_dir(root, "model", "r1", "set", "full")


@pytest.mark.parametrize("status,n,k,u,den,expected", [
    pytest.param("MEETS", 3, 0, .63, 10, .3, id="meets"),
    pytest.param("FAILS", 3, 0, .63, 10, 0., id="fails"),
    pytest.param("UNDERPOWERED", 0, 0, None, 10, 0., id="underpowered-empty"),
    pytest.param("UNDERPOWERED", 3, 2, .9, 10, 0., id="underpowered-accepted"),
    pytest.param("NO_THRESHOLD", None, None, None, 10, 0., id="no-threshold"),
    pytest.param("MEETS", 0, 0, None, 0, 0., id="zero-denominator"),
])
def test_summary_only_tau_two_percent_and_primary(status, n, k, u, den, expected):
    # RiskCell.test 모양을 갖추되, 상태는 위험 재판정 없이 복사하는지 따로 시험한다.
    trial = dict(n_groups=den, n_denom=den, n_empty_mask=0, n_accepted=n, k_errors=k,
        U=u, coverage=dict(num=n or 0, den=den), b_flip=1 if status == "MEETS" and n else None)
    risk = {"cells": {"0.01": {"invalid": "must not read"}, "0.02": dict(tau="0.02", status=status,
        insufficient_by_design=True, test=trial), "0.05": {"invalid": "must not read"}}}
    kwargs = dict(risk=risk, model="m", set="s", variant="full", primary_variant="full", t0_status="partial")
    summary = summary_from_risk(**kwargs)
    assert summary == dict(benchmark="jev:s:full", model="m", metric="coverage_at_risk_2pct",
        score=expected, total=den, status=status, insufficient_by_design=True, t0_status="partial",
        score_rule="meets_only", coverage_observed=dict(num=n or 0, den=den),
        n_accepted=n, k_errors=k, U=u)
    assert summary["coverage_observed"] == trial["coverage"]
    assert summary["coverage_observed"] is not trial["coverage"]
    assert summary_from_risk(**{**kwargs, "variant": "actions_only", "risk": {}}) is None


def test_summary_rejects_tau_mismatch():
    risk = {"cells": {"0.02": {"tau": "0.05"}}}
    with pytest.raises(ValueError, match="summary tau mismatch"):
        summary_from_risk(risk=risk, model="m", set="s", variant="full",
                          primary_variant="full", t0_status="partial")
