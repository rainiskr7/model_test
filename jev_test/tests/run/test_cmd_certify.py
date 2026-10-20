"""인증 a/b/c 독립 실패와 시간 증거 경계."""

import os

import pytest

from jeveval.io import run_files
from jeveval.io.hashes import sha256_file
from jeveval.run import cmd_certify
from tests.run.file_support import output_files


@pytest.mark.parametrize("check", ["a", "b", "c"])
def test_each_certification_check_detects_tampering(h, check):
    h.finish()
    seal_path, threshold_path = h.directory / "test/seal.json", h.directory / "threshold.json"
    seal = run_files.read_json(seal_path)
    if check == "a":
        seal["dev_final_sha256"] = "0" * 64
        run_files.write_json(seal_path, seal)
    elif check == "b":
        threshold = run_files.read_json(threshold_path)
        threshold["by_tau"]["0.02"]["t_star"] = .8
        run_files.write_json(threshold_path, threshold)
        seal["threshold_sha256"] = sha256_file(threshold_path)
        run_files.write_json(seal_path, seal)
        risk = run_files.read_json(h.directory / "risk.json")
        risk["threshold_sha256"] = seal["threshold_sha256"]
        run_files.write_json(h.directory / "risk.json", risk)
    else:
        risk = run_files.read_json(h.directory / "risk.json")
        risk["threshold_sha256"] = "0" * 64
        run_files.write_json(h.directory / "risk.json", risk)
    before = output_files(h.directory)
    result = cmd_certify.run(root=h.root, run_dir=h.directory)
    assert result["ok"] is False
    assert result["checks"] == {name: name != check for name in ("a", "b", "c")}
    assert output_files(h.directory) == before


def test_sealed_at_requires_timezone(h):
    h.finish()
    path = h.directory / "test/seal.json"
    seal = run_files.read_json(path)
    seal["sealed_at"] = "2026-10-17T12:00:00"
    run_files.write_json(path, seal)
    before = output_files(h.directory)
    with pytest.raises(ValueError, match="^seal timestamp requires timezone$"):
        cmd_certify.run(root=h.root, run_dir=h.directory)
    assert output_files(h.directory) == before


def test_mtime_warning_does_not_invalidate_content_checks(h):
    h.finish()
    os.utime(h.directory / "threshold.json", (2_000_000_000, 2_000_000_000))
    result = cmd_certify.run(root=h.root, run_dir=h.directory)
    assert result["ok"] is True and all(result["checks"].values())
    assert "threshold_mtime_after_seal" in result["warnings"]
