"""T0 fixture의 케이스 수, 정책 placements, boundary 참조."""

from copy import deepcopy
import json

import pytest

from jeveval.data.t0_fixture import make_fixture
from tests.t0_io.conftest import ROOT, setup


def test_case_counts_policy_placements_and_boundary(setup):
    ctx = setup()
    template = json.loads((ROOT / "configs/t0/template_v1.json").read_text())
    before = deepcopy(template)
    placements = ["single", "eight_7"]
    result = make_fixture(ctx.sources, template, placements)
    regular = result["cases"][:-1]
    assert len(result["cases"]) == len(ctx.sources.rows) + 2 + len(template["serialization"]) + 1
    assert result["cases"][-1] == dict(case_id="boundary", kind="boundary", offsets=[0, 1],
                                      base_case=regular[0]["case_id"])
    assert len(result["batches"]) == sum(len(case["questions"]) for case in regular)
    assert [batch["target"] for batch in result["batches"]] == [
        [case["case_id"], qid] for case in regular for qid in case["questions"]]
    assert all(batch["placements"] == placements for batch in result["batches"])
    placements.clear()
    assert result["batches"][0]["placements"] == ["single", "eight_7"]
    result["cases"][0]["questions"].clear()
    assert template == before


def test_no_out_of_pool_source_rejected(setup, t0_policy):
    from dataclasses import replace
    ctx = setup()
    sources = replace(ctx.sources, pools={name: set(group.members) for name, group in ctx.sources.groups.items()})
    template = json.loads((ROOT / "configs/t0/template_v1.json").read_text())
    with pytest.raises(ValueError, match="^no out-of-pool T0 source$"):
        make_fixture(sources, template, t0_policy.variants["pplx_v1_1"])


def test_source_state_uses_explicit_family_for_alias():
    from jeveval.data.t0_fixture import source_state
    from jeveval.types import SourceRow
    assert source_state(SourceRow("kosgd2", "d#0", {"dialogue": []}), "kosgd") == "[]"


def test_resolver_excludes_other_alias_pool_in_memory():
    import pytest
    from jeveval.data.t0_fixture import resolve_source
    from jeveval.types import SourceRow, Groups
    from jeveval.types.t0_io import T0Sources
    sources = T0Sources({"kosgd2": [SourceRow("kosgd2", "d#0", {"dialogue": []})]},
        {"kosgd2": Groups({"d#0": "d"}, {"d": ["0"]})},
        {"kosgd": {"d"}, "kosgd2": set()}, 1, {"kosgd": "kosgd", "kosgd2": "kosgd"})
    with pytest.raises(ValueError, match="inside evaluation pool"):
        resolve_source({"set": "kosgd2", "row_id": "d#0"}, sources)
