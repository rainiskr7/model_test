"""무엇: 단계별 입력 격리 · 입력: 합성 FunctionChat·읽기 금지 폴더 · 출력: Item/기록 · 계약 §8-6 E."""

import json
from pathlib import Path
import shutil

import pytest
import yaml

from jeveval.data.grouping import group_rows
from jeveval.data.split import build_split_plan
from jeveval.io.hashes import sha256_file
from jeveval.io.splits import write_split_plan
from jeveval.run.stage_inputs import attempts_path, final_path, load_items, read_stage_finals
from jeveval.types import PoolResult, SourceRow


REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def source(tmp_path):
    shutil.copytree(REPO / "configs/tasks", tmp_path / "configs/tasks")
    data = tmp_path / "dataset/fc_call_decision"
    data.mkdir(parents=True)
    rows = [dict(serial_num=i, input_messages=[dict(role="system", content="system"),
            dict(role="user", content=f"user{min(i, 2)}")], input_tools=[dict(function=dict(
            name=f"tool{min(i, 2)}", description="tool"))], type_of_output="slot", ground_truth={})
            for i in (1, 2, 3)]
    path = data / "rows.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows))
    (data / "SHA256SUMS").write_text(sha256_file(path) + "  rows.jsonl\n")
    cfg = dict(source={"file": "dataset/fc_call_decision/rows.jsonl"},
               group_key="fc_components", pool={"kind": "all"}, extra=True)
    records = [SourceRow("fc_call_decision", str(row["serial_num"]), row) for row in rows]
    groups = group_rows(records, "fc_components")
    plan = build_split_plan(records, groups, PoolResult(sorted(groups.members), {"all": 2}),
                            "fc_call_decision", cfg, 1, .5)
    write_split_plan(plan, tmp_path / "configs/splits/fc_call_decision.json")
    (tmp_path / "configs/splits/rules.yaml").write_text(yaml.safe_dump({"sets": {plan.set: cfg}}))
    return plan


@pytest.mark.parametrize("stage", ["dev", "test", "extra"])
def test_build_real_items_only_requested_stage(tmp_path, source, stage):
    result = load_items(root=tmp_path, task_path="configs/tasks/fc_call_decision.yaml", stage=stage)
    expected = source.extra if stage == "extra" else [source.representative[g] for g in getattr(source, stage)]
    assert [f"{i.set}:{i.group_id}:{i.item_id}" for i in result] == expected
    assert len(result) == 1 and all(q.gold is not None for q in result[0].questions)
    assert final_path(tmp_path, stage) == tmp_path / stage / "final.jsonl"
    assert attempts_path(tmp_path, stage) == tmp_path / stage / "attempts.jsonl"


def test_dev_loader_never_opens_other_stage(tmp_path, source, fixture_json, monkeypatch):
    run = tmp_path / "run"
    for stage in ("dev", "test", "extra"):
        (run / stage).mkdir(parents=True)
    raw = fixture_json("seal/cases.json")["cases"][0]["dev_final_raw"]
    (run / "dev/final.jsonl").write_text(raw + '{"broken":')
    forbidden = [run / "test", run / "extra"]
    for path in forbidden:
        path.chmod(0)
    opened = []
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert not any(path == folder or folder in path.parents for folder in forbidden)
        opened.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    try:
        items = load_items(root=tmp_path, task_path="configs/tasks/fc_call_decision.yaml", stage="dev")
        finals, warnings = read_stage_finals(run, "dev")
        assert len(items) == len(finals) == 1
        assert warnings == ["truncated_last_line"]
        assert run / "dev/final.jsonl" in opened
    finally:
        for path in forbidden:
            path.chmod(0o700)


def test_missing_final_invalid_stage_and_dataset_tamper(tmp_path, source):
    assert read_stage_finals(tmp_path, "dev") == ([], [])
    for stage in ("../test", "", "DEV"):
        with pytest.raises(ValueError):
            load_items(root=tmp_path, task_path="missing.yaml", stage=stage)
        with pytest.raises(ValueError):
            read_stage_finals(tmp_path, stage)
    (tmp_path / "dataset/fc_call_decision/rows.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="dataset hash mismatch"):
        load_items(root=tmp_path, task_path="configs/tasks/fc_call_decision.yaml", stage="dev")
