from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

import pytest

from derive_multimodal_publish import main as derive_cli_main
from shared.multimodal.publish.derive import (
    derive_all,
    native_sidecar_from_source,
    original_artifact_manifest,
    write_sidecar,
)
from shared.multimodal.publish.report import collect, strict_failed


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


def test_tampered_native_artifact_is_not_collected_or_skipped(tmp_path):
    source = _copy_clean_source(tmp_path)
    path = _write_native(source, tmp_path)
    raw = source / "results.json"
    raw.write_text(raw.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    sidecars, missing = collect(tmp_path)
    assert sidecars == []
    assert len(missing) == 1
    assert "손상" in missing[0]["reason"]

    derived = derive_all(tmp_path, write=True)
    assert len(derived) == 1
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["status"] == "REJECTED"
    assert any("artifact 무결성 실패" in reason for reason in stored["failures"])


def test_native_with_missing_source_artifact_is_not_collected(tmp_path):
    source = _copy_clean_source(tmp_path)
    _write_native(source, tmp_path)
    (source / "summary.json").unlink()
    sidecars, missing = collect(tmp_path)
    assert sidecars == []
    assert len(missing) == 1
    assert "artifact missing" in missing[0]["reason"]


def test_concurrent_passive_derive_cannot_overwrite_native(monkeypatch, tmp_path):
    from shared.multimodal.publish import derive as derive_module

    source = _copy_clean_source(tmp_path)
    native_path, native = native_sidecar_from_source(source, tmp_path)
    original_derive_source = derive_module.derive_source
    calculated = threading.Event()
    release = threading.Event()

    def slow_derive(source_path, base):
        item = original_derive_source(source_path, base)
        calculated.set()
        assert release.wait(timeout=5)
        return item

    monkeypatch.setattr(derive_module, "derive_source", slow_derive)
    outcome = []
    worker = threading.Thread(
        target=lambda: outcome.extend(derive_module.derive_all(tmp_path, write=True)),
    )
    worker.start()
    assert calculated.wait(timeout=5)
    write_sidecar(native_path, native)
    release.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert outcome == []
    assert json.loads(native_path.read_text(encoding="utf-8"))["status"] == "NATIVE"


def test_strict_collection_is_scoped_to_requested_partial_session(tmp_path):
    source = _copy_clean_source(tmp_path)
    derive_all(tmp_path, write=True)
    historical = tmp_path / "results/model/old-session/vision/multimodal/k_dtcbench"
    historical.mkdir(parents=True)

    current_session = source.relative_to(tmp_path / "results").parts[1]
    sidecars, missing = collect(tmp_path, current_session)
    assert sidecars and missing == []
    assert strict_failed(sidecars, missing, []) is False

    old_sidecars, old_missing = collect(tmp_path, "old-session")
    assert old_sidecars == [] and len(old_missing) == 1
    assert strict_failed(old_sidecars, old_missing, []) is True
