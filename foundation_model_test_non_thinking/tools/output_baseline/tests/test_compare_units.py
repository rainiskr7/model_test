"""Synthetic manifests only: never read real results or external benches."""

import copy

import pytest

from tools.output_baseline.compare import compare, expected_outputs
from tools.output_baseline.inputs import sha256


@pytest.fixture
def manifest(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    (source / "raw.json").write_text("{}")
    value = {"snapshot": {"root": str(source), "required": ["raw.json"],
                          "files": {"raw.json": sha256(source / "raw.json")}},
             "prerequisite": {"ok": True}, "boundary": {"ok": True}, "errors": [],
             "expected_outputs": ["reports/synthetic.stdout"], "sides": {}}
    for side in ("head", "working"):
        output = tmp_path / side
        output.write_text("same\n")
        value["sides"][side] = {"errors": [], "artifacts": {
            "reports/synthetic.stdout": {"path": str(output), "rc": 0, "sha256": sha256(output)}}}
    return value


def test_identical_and_mutated_artifact(manifest, tmp_path):
    assert compare(manifest)[0] == 0
    (tmp_path / "working").write_text("different\n")
    assert compare(manifest) == (1, ["DIFF: reports/synthetic.stdout"])


@pytest.mark.parametrize("sides", [("head",), ("head", "working")])
def test_missing_output_is_failure_even_on_both_sides(manifest, tmp_path, sides):
    for side in sides:
        (tmp_path / side).unlink()
    rc, messages = compare(manifest)
    assert rc == 2
    assert any("missing output: reports/synthetic.stdout" in message for message in messages)


def test_missing_input_is_failure(manifest, tmp_path):
    (tmp_path / "input/raw.json").unlink()
    rc, messages = compare(manifest)
    assert rc == 2
    assert "missing input: raw.json" in messages


@pytest.mark.parametrize("field", ["prerequisite", "boundary"])
def test_preconditions_are_required(manifest, field):
    manifest[field]["ok"] = False
    assert compare(manifest)[0] == 2


def test_equal_execution_failure_is_not_equal_output(manifest):
    for side in manifest["sides"].values():
        side["artifacts"]["reports/synthetic.stdout"]["rc"] = 2
    assert compare(manifest)[0] == 2


def test_agent_rc_is_part_of_comparison(manifest):
    value = copy.deepcopy(manifest)
    value["expected_outputs"] = ["agent/session/stdout"]
    for side in value["sides"].values():
        side["artifacts"]["agent/session/stdout"] = side["artifacts"].pop("reports/synthetic.stdout")
    value["sides"]["head"]["artifacts"]["agent/session/stdout"]["rc"] = 3
    assert compare(value) == (1, ["DIFF: agent/session/stdout"])


def test_expected_outputs_cover_all_stages():
    names = expected_outputs([{"kind": kind, "path": "results/" + kind}
                              for kind in ("agent", "taubench", "functionchat", "multimodal")])
    assert len(names) == len(set(names)) == 9
    assert "agent/results/agent/stdout" in names
    assert "multimodal/results/multimodal/sidecar.json" in names
