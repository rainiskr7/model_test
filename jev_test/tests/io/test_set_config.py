"""무엇: 설정 조회 격리 · 입력: 합성 공용/overlay · 출력: 단일 읽기·전체 거부 · 계약 판 5 보정 1 §9."""

from pathlib import Path
import shutil

import pytest

from jeveval.io import set_config
from jeveval.io.config import read_yaml
from tests.run.cli_support import Harness, REPO, put_yaml


def test_base_entry_never_opens_overlay_directory(tmp_path, monkeypatch):
    h = Harness(tmp_path)
    before = set_config.entry(tmp_path, h.set)
    (tmp_path / "configs/sets").mkdir()
    (tmp_path / "configs/sets/bad.yaml").write_text("broken: [")
    original = Path.open
    def guarded(path, *args, **kwargs):
        assert "sets" not in path.parts
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    assert set_config.entry(tmp_path, h.set) == before


def test_alias_reads_only_own_overlay_and_checks_declared_tasks(tmp_path):
    h = Harness(tmp_path, "kosgd2", "full")
    (tmp_path / "configs/sets/bad.yaml").write_text("schema: wrong")
    selected = set_config.entry(tmp_path, h.set)
    assert selected.family == "kosgd" and selected.overlay_path == "configs/sets/kosgd2.yaml"
    assert len(selected.task_files) == 2
    with pytest.raises(ValueError):
        set_config.catalog(tmp_path)
    (tmp_path / selected.task_files[0]).unlink()
    with pytest.raises(OSError):
        set_config.entry(tmp_path, h.set)


def test_base_redefinition_rejected_by_catalog_only(tmp_path):
    h = Harness(tmp_path)
    before = set_config.entry(tmp_path, h.set)
    value = read_yaml(REPO / "configs/sets/kosgd2.yaml")
    value["id"] = value["dataset"]["id"] = h.set
    put_yaml(tmp_path / f"configs/sets/{h.set}.yaml", value)
    assert set_config.entry(tmp_path, h.set) == before
    with pytest.raises(ValueError):
        set_config.catalog(tmp_path)


def test_custom_base_paths_and_evidence_paths(tmp_path):
    h = Harness(tmp_path, "kosgd2", "full")
    for name in ("datasets", "rules"):
        original = tmp_path / ("configs/datasets.yaml" if name == "datasets" else "configs/splits/rules.yaml")
        shutil.move(original, tmp_path / f"custom_{name}.yaml")
    selected = set_config.entry(tmp_path, h.set, datasets="custom_datasets.yaml", rules="custom_rules.yaml")
    assert set_config.catalog(tmp_path, datasets="custom_datasets.yaml", rules="custom_rules.yaml")[-1] == selected
    assert set(set_config.evidence_paths(selected)) == {selected.overlay_path, *selected.task_files}
    assert set_config.evidence_paths(set_config.entry(REPO, "kosgd")) == ()


def test_repository_overlay_evidence_and_defensive_copy():
    selected = set_config.entry(REPO, "kosgd2")
    assert {"audits/kosgd2_selection/selection.json", "audits/kosgd_audit/audit_result.json",
            "configs/t0/fixture_v1.json"} <= set(set_config.evidence_paths(selected))
    selected.dataset["map"]["primary_variant"] = "changed"
    assert set_config.entry(REPO, "kosgd2").dataset["map"]["primary_variant"] == "full"



def test_explicit_public_config_paths_keep_external_path_support(tmp_path):
    root = tmp_path / "repo"
    h = Harness(root)
    before = set_config.entry(root, h.set)
    for name, old in (("data", "configs/datasets.yaml"), ("rules", "configs/splits/rules.yaml")):
        shutil.move(root / old, tmp_path / f"{name}.yaml")
    assert set_config.entry(root, h.set, datasets=tmp_path / "data.yaml", rules="../rules.yaml") == before


def test_registered_overlay_manifest_is_evidence_without_changing_base():
    selected = set_config.entry(REPO, "kosgd2")
    assert selected.analysis == "configs/analysis/question_risk_v2.yaml"
    assert selected.analysis in set_config.evidence_paths(selected)
    assert set_config.entry(REPO, "kosgd").analysis is None
