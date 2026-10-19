import pytest

from tools.output_baseline.inputs import validate_snapshot
from tools.output_baseline.snapshot import copy_inputs


def test_copy_snapshot_includes_sibling_hashes_and_detects_mutation(tmp_path):
    base, target = tmp_path / "base", tmp_path / "snapshot"
    for name in ("configs/model_identity.json", "results/m/koffvqa/summary.json",
                 "results/m/koffvqa/test_gen.xlsx", "results/m/koffvqa_api_judge/results.json"):
        path = base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic")
    record = copy_inputs(base, target, [{"kind": "multimodal", "path": "results/m/koffvqa_api_judge"}])
    assert len(record["files"]) == 4
    assert validate_snapshot(record) == []
    (target / "results/m/koffvqa/summary.json").write_text("changed")
    assert validate_snapshot(record) == ["changed input: results/m/koffvqa/summary.json"]


def test_new_snapshot_file_is_not_silently_shared_between_sides(tmp_path):
    (tmp_path / "extra.json").write_text("{}")
    record = {"root": str(tmp_path), "required": [], "files": {}}
    assert "unexpected input file: extra.json" in validate_snapshot(record)


def test_copy_missing_input_fails(tmp_path):
    with pytest.raises(FileNotFoundError, match="missing input"):
        copy_inputs(tmp_path, tmp_path / "snapshot", [{"kind": "agent", "path": "results/missing"}])


def test_kreta_companions_are_copied_but_listed_source_is_required(tmp_path):
    base = tmp_path / "base"
    for name in ("configs/model_identity.json", "results/m/kreta/a.jsonl",
                 "results/m/kreta/results.json", "results/m/kreta/run_config.json"):
        path = base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
    entries = [{"kind": "multimodal", "path": "results/m/kreta/a.jsonl"}]
    record = copy_inputs(base, tmp_path / "snapshot", entries)
    assert set(record["files"]) == {"configs/model_identity.json", "results/m/kreta/a.jsonl",
                                    "results/m/kreta/results.json", "results/m/kreta/run_config.json"}
    (base / "results/m/kreta/a.jsonl").unlink()
    with pytest.raises(FileNotFoundError, match="a.jsonl"):
        copy_inputs(base, tmp_path / "missing", entries)
