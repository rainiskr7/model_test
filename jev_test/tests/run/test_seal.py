"""무엇: 봉인 바이트/fixture 대조 · 입력: 기존 seal 사례 · 출력: 해시·resume 거부 · 계약 §5-7."""

import os

import pytest

from jeveval.io.hashes import sha256_file
from jeveval.run.gate import prepare_stage
from jeveval.run.seal import check_seal, write_seal
from tests.run.stage_support import install_case, plan_for, snapshot


def test_write_hashes_no_overwrite_and_mtime_ignored(tmp_path, fixture_json):
    case = fixture_json("seal/cases.json")["cases"][0]
    install_case(tmp_path, case)
    seal = write_seal(tmp_path, now="now")
    assert seal == dict(threshold_sha256=sha256_file(tmp_path / "threshold.json"),
                        dev_final_sha256=sha256_file(tmp_path / "dev/final.jsonl"), sealed_at="now")
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match="already exists"):
        write_seal(tmp_path, now="later")
    assert snapshot(tmp_path) == before
    os.utime(tmp_path / "threshold.json", (99, 99))
    assert check_seal(tmp_path) == []


@pytest.mark.parametrize("name", ["unchanged", "mtime_only", "tampered", "hash_mismatch",
                                  "missing_threshold", "dev_changed"])
def test_existing_seal_fixture_hash_checks_and_resume(tmp_path, fixture_json, name):
    case = next(c for c in fixture_json("seal/cases.json")["cases"] if c["name"] == name)
    install_case(tmp_path, case, sealed=True)
    expected = {"unchanged": [], "mtime_only": [], "tampered": ["threshold_sha256"],
                "hash_mismatch": ["threshold_sha256"], "missing_threshold": ["threshold_sha256"],
                "dev_changed": ["dev_final_sha256"]}[name]
    assert check_seal(tmp_path) == expected
    before = snapshot(tmp_path)
    kwargs = dict(run_dir=tmp_path, stage="test", fingerprint={"run_id": "r1"}, plan=plan_for(), now="now")
    if expected:
        with pytest.raises(ValueError):
            prepare_stage(**kwargs)
        assert snapshot(tmp_path) == before
    else:
        assert prepare_stage(**kwargs) == []
        assert snapshot(tmp_path)["test/seal.json"] == before["test/seal.json"]


def test_missing_threshold_or_dev_never_writes(tmp_path):
    assert check_seal(tmp_path) == []
    for threshold in (False, True):
        if threshold:
            (tmp_path / "threshold.json").write_text("{}")
        before = snapshot(tmp_path)
        with pytest.raises(ValueError):
            write_seal(tmp_path, now="now")
        assert snapshot(tmp_path) == before
