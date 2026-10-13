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


@pytest.mark.parametrize("status,den,expected", [("MEETS", 10, .3), ("FAILS", 10, .3),
    ("UNDERPOWERED", 10, 0.), ("NO_THRESHOLD", 10, 0.), ("MEETS", 0, 0.)])
def test_summary_only_tau_two_percent_and_primary(status, den, expected):
    risk = {"cells": {"0.01": {"invalid": "must not read"}, "0.02": dict(tau="0.02", status=status,
        insufficient_by_design=True, test={"coverage": {"num": 3, "den": den}, "n_denom": den})}}
    kwargs = dict(risk=risk, model="m", set="s", variant="full", primary_variant="full", t0_status="partial")
    summary = summary_from_risk(**kwargs)
    assert summary == dict(benchmark="jev:s:full", model="m", metric="coverage_at_risk_2pct",
        score=expected, total=den, status=status, insufficient_by_design=True, t0_status="partial")
    assert summary_from_risk(**{**kwargs, "variant": "actions_only", "risk": {}}) is None
