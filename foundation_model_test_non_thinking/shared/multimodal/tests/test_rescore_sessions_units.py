"""입력: tmp_path 세션·출력 경로. 출력: SHA·revision·쓰기 경계 검증."""

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from shared.multimodal.rescore.manifest import DATASETS
from shared.multimodal.rescore.sessions import (
    check_revisions, discover_sources, read_session, rescore_source, validate_output, write_output,
)
from shared.multimodal.tests.test_rescore_kmmbench_circular_units import circular_case


def session_case(tmp_path):
    rows, manifest = circular_case()
    source = tmp_path / "results/model/run/vision/multimodal/k_mmbench"
    source.mkdir(parents=True)
    (source / "results.json").write_text(json.dumps(rows))
    (source / "summary.json").write_text(json.dumps({"run_config": {"dataset": {
        "revision": manifest["revision"], "huggingface_id": manifest["dataset"]}}}))
    directory = tmp_path / "manifests"
    directory.mkdir()
    (directory / f'k_mmbench_{manifest["revision"]}.json').write_text(json.dumps(manifest))
    return source, directory


def test_read_and_discover_and_rescore_only_use_fixed_input_files(tmp_path):
    source, directory = session_case(tmp_path)
    (source / "_derived/k_mmbench").mkdir(parents=True)
    (source / "_derived/k_mmbench/results.json").write_text("[]")
    assert discover_sources(tmp_path) == [source]
    rows, dataset, hashes = read_session(source)
    assert dataset["revision"] == DATASETS["k_mmbench"][1]
    assert hashes["results.json"] == hashlib.sha256((source / "results.json").read_bytes()).hexdigest()
    result = rescore_source(source, directory)
    assert result["accepted"] is True and result["accuracy"] == 1
    assert len(rows) == 9 and len(result["manifest_sha256"]) == 64


@pytest.mark.parametrize("area", ["results", "data", "logs"])
def test_protected_output_and_symlink_are_rejected_before_mkdir(tmp_path, area):
    protected = tmp_path / area
    protected.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(protected, target_is_directory=True)
    for path in (protected / "nested/out.json", alias / "nested/out.json"):
        with pytest.raises(ValueError):
            write_output(path, {}, tmp_path)
    assert not (protected / "nested").exists()


def test_external_output_is_sorted_atomic_and_cannot_replace_source(tmp_path):
    target = tmp_path / "analysis/out.json"
    write_output(target, {"z": 1, "a": {"z": 2, "a": "한글"}}, tmp_path)
    assert target.read_text() == '{\n  "a": {\n    "a": "한글",\n    "z": 2\n  },\n  "z": 1\n}\n'
    with pytest.raises(ValueError):
        validate_output(tmp_path / "input/out.json", tmp_path, [tmp_path / "input"])
    assert [p.name for p in target.parent.iterdir()] == ["out.json"]


def test_revision_check_uses_tracked_summary_only(tmp_path):
    source, _ = session_case(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "results"], check=True)
    revision = DATASETS["k_mmbench"][1]
    assert check_revisions(tmp_path, "k_mmbench", revision) == 1
    (source / "summary.json").write_text('{"run_config": {"dataset": {"revision": "other"}}}')
    with pytest.raises(ValueError, match="revision"):
        check_revisions(tmp_path, "k_mmbench", revision)


def test_wrong_dataset_identity_rejected(tmp_path):
    source, directory = session_case(tmp_path)
    summary = json.loads((source / "summary.json").read_text())
    summary["run_config"]["dataset"]["huggingface_id"] = "other/dataset"
    (source / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="dataset"):
        rescore_source(source, directory)
