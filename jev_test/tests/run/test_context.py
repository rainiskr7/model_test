"""무엇: 명령 문맥 경계 · 입력: Harness 합성 실행 · 출력: 복원/단계 dataclass · 계약 §8-1·§8-6 E/F."""

from dataclasses import replace

import pytest

from jeveval.io import records, run_files
from jeveval.run import context
from jeveval.types import RunContext, StageData
from tests.run.cli_support import Harness, put_yaml


@pytest.fixture
def h(tmp_path, monkeypatch):
    harness = Harness(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JEV_TEST_KEY", "synthetic-key")
    return harness


@pytest.fixture
def configured(h):
    return context.configuration(h.root, h.args["model"], h.args["task"])


@pytest.fixture
def restored(h):
    h.run("dev")
    return context.restore(h.root, h.directory)


def test_configuration_returns_unrestored_run_context(h, configured):
    assert isinstance(configured, RunContext)
    assert configured.root == h.root.resolve()
    assert configured.model_path == h.root / h.args["model"]
    assert configured.task_path == h.root / h.args["task"]
    assert configured.cfg.id == "synthetic"
    assert (configured.task.set, configured.task.variant) == (h.set, h.variant)
    assert configured.plan == h.plan
    assert configured.directory is None and configured.fingerprint is None


@pytest.mark.parametrize("operation", ["identity", "check_identity", "stage"])
def test_unrestored_context_rejected(configured, operation):
    args = {"identity": (), "check_identity": ({},), "stage": ("dev",)}[operation]
    with pytest.raises(ValueError, match="^context is not restored$"):
        getattr(context, operation)(configured, *args)


def test_restore_returns_run_context_with_identity(h, restored):
    assert isinstance(restored, RunContext)
    assert restored.directory == h.directory
    assert restored.fingerprint == run_files.read_json(h.directory / "fingerprint.json")
    expected = dict(model="synthetic", set=h.set, variant=h.variant, run_id="r1")
    assert context.identity(restored) == expected
    assert context.check_identity(restored, expected) is None
    with pytest.raises(ValueError, match="^result identity mismatch$"):
        context.check_identity(restored, {**expected, "run_id": "other"})


@pytest.mark.parametrize("changed", ["files", "code_sha256"])
def test_restore_rejects_fingerprint_mismatch(h, restored, changed):
    path = h.directory / "fingerprint.json"
    saved = run_files.read_json(path)
    if changed == "files":
        key = h.args["task"]
        saved["files"][key] = "0" * 64 if saved["files"][key] != "0" * 64 else "1" * 64
    else:
        saved[changed] = "0" * 64 if saved[changed] != "0" * 64 else "1" * 64
    run_files.write_json(path, saved)
    with pytest.raises(ValueError, match="^frozen inputs differ$"):
        context.restore(h.root, h.directory)


def test_stage_returns_stage_data_with_matching_ids(h, restored):
    data = context.stage(restored, "dev")
    expected = {h.plan.representative[group] for group in h.plan.dev}
    assert isinstance(data, StageData)
    assert {row.logical_id for row in data.finals} == set(data.items) == expected
    assert {row.logical_id for row in data.outcomes} == expected
    assert all(row.stage == "dev" for row in data.outcomes)
    assert all(f"{item.set}:{item.group_id}:{item.item_id}" == lid for lid, item in data.items.items())
    assert data.warnings == []


@pytest.mark.parametrize("mismatch", ["missing", "unexpected"])
def test_stage_rejects_final_ids_outside_split(h, restored, mismatch):
    path = h.directory / "dev/final.jsonl"
    finals, _ = records.read_finals(path)
    changed = [] if mismatch == "missing" else [replace(finals[0], logical_id=f"{h.set}:other:other")]
    path.write_bytes(b"".join(records.record_line(row) for row in changed))
    with pytest.raises(ValueError, match="^stage is incomplete$"):
        context.stage(restored, "dev")


def test_primary_variant_prefers_dataset_mapping(h, configured):
    put_yaml(h.root / "configs/datasets.yaml",
             {"sets": [{"id": h.set, "map": {"primary_variant": "declared"}}]})
    assert context.primary_variant(configured) == "declared"


def test_primary_variant_falls_back_to_single_task_variant(configured):
    assert context.primary_variant(configured) == "default"


def test_completed_rejects_missing_seal(h):
    h.run("dev")
    assert h.command("threshold") == 0
    h.run("test")
    ctx, stages, threshold = context.completed(h.root, h.directory)
    assert isinstance(ctx, RunContext) and set(stages) == {"dev", "test"}
    assert threshold.run_id == "r1"
    (h.directory / "test/seal.json").unlink()
    with pytest.raises(ValueError, match="^valid seal required$"):
        context.completed(h.root, h.directory)
