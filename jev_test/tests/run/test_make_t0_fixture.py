"""fixture CLI는 선택한 정책의 placements를 전달한다."""

import json

from jeveval.io.config import read_yaml
from jeveval.run import make_t0_fixture
from tests.run.cli_support import put_yaml
from tests.t0_io.conftest import ROOT, setup


def test_cli_uses_selected_policy_placements(setup, monkeypatch, capsys):
    ctx = setup()
    template = ctx.root / "template.json"
    template.write_bytes((ROOT / "configs/t0/template_v1.json").read_bytes())
    policy = read_yaml(ctx.root / "configs/t0/tolerance_v1.yaml")
    policy["variants"]["pplx_v1_1"] = ["single", "eight_7"]
    put_yaml(ctx.root / "custom.yaml", policy)
    roots = []
    def sources(root):
        roots.append(root)
        return ctx.sources
    monkeypatch.setattr(make_t0_fixture, "read_sources", sources)
    assert make_t0_fixture.main(["--root", str(ctx.root), "--template", "template.json",
        "--out", "generated.json", "--tolerance-policy", "custom.yaml"]) == 0
    result = json.loads((ctx.root / "generated.json").read_text())
    assert roots == [ctx.root] and result["batches"]
    assert all(b["placements"] == ["single", "eight_7"] for b in result["batches"])
    assert "cases" in capsys.readouterr().out
