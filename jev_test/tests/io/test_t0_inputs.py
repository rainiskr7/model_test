"""무엇: fixture/입력 동결 경계 · 입력: 합성 공개 행·분할 · 출력: 풀/해시/직렬화 검사 · 계약 T-a/c."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json

import pytest

from jeveval.data.grouping import group_rows
from jeveval.data.t0_fixture import make_fixture
from jeveval.io.t0_files import write_fixture
from jeveval.io.t0_inputs import load
from jeveval.types import SourceRow
from tests.t0_io.support import ROOT, inputs, setup


def test_fixture_coverage_and_determinism(setup, t0_policy):
    ctx = setup()
    template = json.loads((ROOT / "configs/t0/template_v1.json").read_text())
    fixture = make_fixture(ctx.sources, template, t0_policy.variants["pplx_v1_1"])
    assert fixture == make_fixture(ctx.sources, template, t0_policy.variants["pplx_v1_1"])
    questions = [q for c in fixture["cases"] for q in c.get("questions", {}).values()]
    assert {len(q["criteria"]) for q in questions if q["type"] == "choice"} == {2, 8, 16}
    assert {len(q["criteria"]) for q in questions if q["type"] == "score"} == {3, 5}
    assert {8, 17} <= {len(c.get("questions", {})) for c in fixture["cases"]}
    choice = next(q for q in questions if q["type"] == "choice")
    assert list(choice["criteria"]) != sorted(choice["criteria"])
    assert {"NONE", "서비스/의도"} <= choice["criteria"].keys()
    write_fixture(ctx.root / "fixture.json", fixture)
    inputs(ctx)
    bundle = load(ctx.directory / "inputs.jsonl")
    by_id = {r.case_id:r.body for r in bundle.rows}
    for cid, state in template["serialization"].items():
        assert json.loads(by_id[cid]["state"])["text"] == state
    with pytest.raises(ValueError, match="already frozen"):
        inputs(ctx)


def test_pool_recheck_rejects_different_row_in_same_group(setup):
    ctx = setup()
    case = ctx.fixture["cases"][0]
    rid = case["state_ref"]["row_id"]
    source = next(r for r in ctx.sources.rows["kmhas"] if r.row_id == rid)
    duplicate = SourceRow("kmhas", "99", dict(source.fields))
    rows = ctx.sources.rows["kmhas"] + [duplicate]
    groups = group_rows(rows, "text")
    ctx.sources = replace(ctx.sources, rows={"kmhas":rows}, groups={"kmhas":groups},
                          pools={"kmhas":{groups.row_to_group[duplicate.row_id]}})
    with pytest.raises(ValueError, match="inside evaluation pool"):
        inputs(ctx)
    assert not (ctx.directory / "inputs.jsonl").exists()


def test_source_hash_and_forbidden_source_rejected(setup):
    ctx = setup()
    fixture = deepcopy(ctx.fixture)
    fixture["cases"][0]["state_sha256"] = "0" * 64
    write_fixture(ctx.root / "fixture.json", fixture)
    with pytest.raises(ValueError, match="source hash"):
        inputs(ctx)
    fixture["cases"][0]["state_ref"]["set"] = "143.private"
    write_fixture(ctx.root / "fixture.json", fixture)
    with pytest.raises(ValueError, match="source set"):
        inputs(ctx)


def test_committed_fixture_has_only_source_ids_and_hashes():
    fixture = json.loads((ROOT / "configs/t0/fixture_v1.json").read_text())
    cases = [c for c in fixture["cases"] if "state_ref" in c]
    assert len(cases) == 7
    assert len({(c["state_ref"]["set"], c["state_ref"]["row_id"]) for c in cases}) == 5
    assert all(set(c) == {"case_id", "state_ref", "state_sha256", "questions", "purpose"} for c in cases)
    assert all(len(c["state_sha256"]) == len(sha256(b"").hexdigest()) for c in cases)
