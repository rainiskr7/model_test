from __future__ import annotations

import json
import shutil
from pathlib import Path

from shared.multimodal.publish.derive import derive_all, original_artifact_manifest


REPO = Path(__file__).resolve().parents[3]


def test_write_only_adds_derived_and_preserves_original_hashes(tmp_path):
    source = REPO / "results/qwen_qwen3.5_35b_a3b_fp8/20260711_003523/vision/multimodal/k_dtcbench"
    target = tmp_path / source.relative_to(REPO)
    target.parent.mkdir(parents=True)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("_derived"))
    before = original_artifact_manifest(tmp_path)
    derived = derive_all(tmp_path, write=True)
    after = original_artifact_manifest(tmp_path)
    assert before == after
    assert len(derived) == 1
    out_path, sidecar = derived[0]
    assert out_path.is_file()
    assert "_derived" in out_path.parts
    assert json.loads(out_path.read_text(encoding="utf-8"))["status"] == sidecar["status"]


def test_dry_run_creates_nothing(tmp_path):
    source = REPO / "results/qwen_qwen3.5_35b_a3b_fp8/20260711_003523/vision/multimodal/k_dtcbench"
    target = tmp_path / source.relative_to(REPO)
    target.parent.mkdir(parents=True)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("_derived"))
    derive_all(tmp_path, write=False)
    assert not (target / "_derived").exists()
