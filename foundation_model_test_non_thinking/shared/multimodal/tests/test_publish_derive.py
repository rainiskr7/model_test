from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from derive_multimodal_publish import main as derive_cli_main
from shared.multimodal.publish.derive import (
    derive_all,
    native_sidecar_from_source,
    original_artifact_manifest,
    write_sidecar,
)


REPO = Path(__file__).resolve().parents[3]


def _copy_clean_source(tmp_path: Path) -> Path:
    source = REPO / "results/qwen_qwen3.5_35b_a3b_fp8/20260711_003523/vision/multimodal/k_dtcbench"
    target = tmp_path / source.relative_to(REPO)
    target.parent.mkdir(parents=True)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("_derived"))
    return target


def _write_native(source: Path, base: Path, completed_at: str = "2026-08-24T00:00:00+00:00") -> Path:
    path, sidecar = native_sidecar_from_source(source, base)
    assert sidecar["status"] == "NATIVE"
    sidecar["completed_at_utc"] = completed_at
    write_sidecar(path, sidecar)
    return path


def test_write_only_adds_derived_and_preserves_original_hashes(tmp_path):
    target = _copy_clean_source(tmp_path)
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
    target = _copy_clean_source(tmp_path)
    derive_all(tmp_path, write=False)
    assert not (target / "_derived").exists()


def test_derive_all_preserves_native_status_and_completed_at(tmp_path):
    source = _copy_clean_source(tmp_path)
    completed_at = "2026-08-24T12:34:56+00:00"
    path = _write_native(source, tmp_path, completed_at)
    skipped = []
    derived = derive_all(
        tmp_path,
        write=True,
        on_native_skip=lambda skipped_path, sidecar: skipped.append((skipped_path, sidecar)),
    )
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert derived == []
    assert [item[0] for item in skipped] == [path]
    assert stored["status"] == "NATIVE"
    assert stored["completed_at_utc"] == completed_at


def test_force_overwrites_native_with_legacy_and_reports_loss(tmp_path):
    source = _copy_clean_source(tmp_path)
    completed_at = "2026-08-24T12:34:56+00:00"
    path = _write_native(source, tmp_path, completed_at)
    warned = []
    derived = derive_all(
        tmp_path,
        write=True,
        force=True,
        on_native_overwrite=lambda warned_path, sidecar: warned.append((warned_path, sidecar)),
    )
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert len(derived) == 1
    assert warned[0][0] == path
    assert warned[0][1]["completed_at_utc"] == completed_at
    assert warned[0][1]["protocol"]["recorded"]
    assert stored["status"] == "LEGACY_REVALIDATED"


@pytest.mark.parametrize("existing_status", ["LEGACY_REVALIDATED", "REJECTED"])
def test_native_write_can_promote_legacy_or_rejected(existing_status, tmp_path):
    source = _copy_clean_source(tmp_path)
    derived = derive_all(tmp_path, write=True)
    path, legacy = derived[0]
    if existing_status == "REJECTED":
        legacy["status"] = "REJECTED"
        legacy["publishable"] = False
        legacy["failures"] = ["synthetic rejection"]
        write_sidecar(path, legacy)
    native_path, native = native_sidecar_from_source(source, tmp_path)
    write_sidecar(native_path, native)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["status"] == "NATIVE"
    assert stored["publishable"] is True


def test_cli_skips_native_by_default_and_force_warns_before_overwrite(tmp_path, capsys):
    source = _copy_clean_source(tmp_path)
    completed_at = "2026-08-24T12:34:56+00:00"
    path = _write_native(source, tmp_path, completed_at)
    assert derive_cli_main(["--base", str(tmp_path), "--write"]) == 0
    skipped_output = capsys.readouterr()
    assert "skipped 1 existing NATIVE sidecar(s)" in skipped_output.out
    assert json.loads(path.read_text(encoding="utf-8"))["completed_at_utc"] == completed_at

    assert derive_cli_main(["--base", str(tmp_path), "--write", "--force"]) == 0
    forced_output = capsys.readouterr()
    assert "completed_at_utc='2026-08-24T12:34:56+00:00'" in forced_output.err
    assert "protocol provenance=" in forced_output.err
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "LEGACY_REVALIDATED"
