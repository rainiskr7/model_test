"""무엇: 진입·복구 순서 검증 · 입력: 기존 resume/seal fixture · 출력: 경고·거부/불변 · 계약 §8-6 A/E."""

from dataclasses import replace
import json

import pytest

from jeveval.io.records import read_attempts
from jeveval.io.run_files import read_json
from jeveval.run.gate import prepare_stage
from jeveval.run.seal import check_seal
from tests.run.stage_support import install_case, plan_for, put, snapshot


def enter(root, *, stage="test", fingerprint=None, plan=None):
    return prepare_stage(run_dir=root, stage=stage, fingerprint=fingerprint or {"run_id": "r1"},
                         plan=plan or plan_for(), now="now")


def test_fingerprint_fixture_and_broken_tail_order(tmp_path, fixture_json):
    fp = fixture_json("resume/fingerprint.json")
    broken = fixture_json("resume/broken_last_line.json")
    put(tmp_path, "fingerprint.json", json.dumps(fp["existing"]))
    attempts = put(tmp_path, "dev/attempts.jsonl", broken["attempts_jsonl"])
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        enter(tmp_path, stage="dev", fingerprint=fp["different"])
    assert snapshot(tmp_path) == before
    assert enter(tmp_path, stage="dev", fingerprint=fp["same"]) == ["truncated_last_line"]
    records, warnings = read_attempts(attempts)
    assert [r.to_dict() for r in records] == broken["expected"]["kept_attempts"]
    assert warnings == []
    assert read_json(tmp_path / "fingerprint.json") == fp["existing"]


@pytest.mark.parametrize("name", ["unchanged", "mtime_only", "tampered", "hash_mismatch",
                                  "missing_threshold", "dev_changed"])
def test_seal_fixture_first_start(tmp_path, fixture_json, name):
    case = next(c for c in fixture_json("seal/cases.json")["cases"] if c["name"] == name)
    # start_allowed는 봉인 전 첫 진입. fixture의 seal은 아래 resume 시험에 따로 사용한다.
    install_case(tmp_path, case)
    before = snapshot(tmp_path)
    if case["expected"]["start_allowed"]:
        warnings = enter(tmp_path)
        assert warnings == (["truncated_last_line"] if name == "dev_changed" else [])
        assert check_seal(tmp_path) == []
        assert (tmp_path / "dev/final.jsonl").read_bytes() == before["dev/final.jsonl"]
    else:
        with pytest.raises(ValueError):
            enter(tmp_path)
        assert snapshot(tmp_path) == before


def test_threshold_replaced_fixture_refuses_without_repair(tmp_path, fixture_json):
    case = fixture_json("seal/cases.json")["cases"][0]
    replaced = fixture_json("resume/threshold_replaced.json")
    install_case(tmp_path, case, sealed=True)
    put(tmp_path, "threshold.json", replaced["current_threshold_raw"])
    put(tmp_path, "test/seal.json", json.dumps(replaced["seal"]))
    put(tmp_path, "test/attempts.jsonl", fixture_json("resume/broken_last_line.json")["attempts_jsonl"])
    before = snapshot(tmp_path)
    assert replaced["expected"]["resume_allowed"] is False
    with pytest.raises(ValueError):
        enter(tmp_path)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("failure", ["missing_dev", "unexpected_dev", "duplicate_dev",
    "middle_attempt", "middle_final", "invalid_record", "invalid_fingerprint", "invalid_seal",
    "threshold_missing", "dev_changed", "invalid_stage"])
def test_every_rejection_preserves_whole_directory(tmp_path, fixture_json, failure):
    case = fixture_json("seal/cases.json")["cases"][0]
    install_case(tmp_path, case, sealed=True)
    put(tmp_path, "test/attempts.jsonl", fixture_json("resume/broken_last_line.json")["attempts_jsonl"])
    put(tmp_path, "test/final.jsonl", '{"unfinished":')
    if failure == "missing_dev":
        (tmp_path / "dev/final.jsonl").unlink()
    elif failure == "unexpected_dev":
        put(tmp_path, "dev/final.jsonl", case["dev_final_raw"].replace("synthetic:g:ok", "PRIVATE_SOURCE"))
    elif failure == "duplicate_dev":
        put(tmp_path, "dev/final.jsonl", case["dev_final_raw"] * 2)
    elif failure.startswith("middle_"):
        name = "attempts" if failure == "middle_attempt" else "final"
        put(tmp_path, f"test/{name}.jsonl", 'PRIVATE_SOURCE\n{}\n')
    elif failure == "invalid_record":
        put(tmp_path, "test/final.jsonl", '{}\n')
    elif failure == "invalid_fingerprint":
        put(tmp_path, "fingerprint.json", '{"PRIVATE_SOURCE":')
    elif failure == "invalid_seal":
        put(tmp_path, "test/seal.json", '["PRIVATE_SOURCE"]')
    elif failure == "threshold_missing":
        (tmp_path / "threshold.json").unlink()
    elif failure == "dev_changed":
        put(tmp_path, "dev/final.jsonl", case["dev_final_raw"] + "\n")
    before = snapshot(tmp_path)
    with pytest.raises(ValueError) as caught:
        enter(tmp_path, stage="PRIVATE_SOURCE" if failure == "invalid_stage" else "test")
    assert "PRIVATE_SOURCE" not in str(caught.value)
    assert snapshot(tmp_path) == before


def test_extra_requires_exact_test_set_and_existing_seal_integrity(tmp_path, fixture_json):
    case = fixture_json("seal/cases.json")["cases"][0]
    install_case(tmp_path, case, sealed=True)
    for raw in ("", case["dev_final_raw"], case["dev_final_raw"] * 2):
        put(tmp_path, "test/final.jsonl", raw)
        before = snapshot(tmp_path)
        with pytest.raises(ValueError):
            enter(tmp_path, stage="extra")
        assert snapshot(tmp_path) == before
    put(tmp_path, "test/final.jsonl", case["dev_final_raw"].replace("synthetic:g:ok", "synthetic:t:i"))
    seal_before = (tmp_path / "test/seal.json").read_bytes()
    assert enter(tmp_path, stage="extra") == []
    assert (tmp_path / "test/seal.json").read_bytes() == seal_before
    put(tmp_path, "threshold.json", "changed")
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        enter(tmp_path, stage="extra")
    assert snapshot(tmp_path) == before


def test_success_repairs_only_current_stage_and_keeps_seal(tmp_path, fixture_json):
    case = fixture_json("seal/cases.json")["cases"][0]
    install_case(tmp_path, case, sealed=True)
    put(tmp_path, "test/final.jsonl", case["dev_final_raw"].rstrip("\n"))
    put(tmp_path, "extra/final.jsonl", "do not read or repair")
    before = snapshot(tmp_path)
    assert enter(tmp_path) == ["missing_final_newline"]
    after = snapshot(tmp_path)
    for name in ("test/seal.json", "dev/final.jsonl", "extra/final.jsonl"):
        assert after[name] == before[name]
    assert enter(tmp_path) == []


def test_dev_fresh_run_and_empty_dev_missing_file_rejected(tmp_path):
    root = tmp_path / "new"
    assert enter(root, stage="dev") == []
    assert read_json(root / "fingerprint.json") == {"run_id": "r1"}
    put(root, "threshold.json", "{}")
    before = snapshot(root)
    with pytest.raises(ValueError):
        enter(root, plan=replace(plan_for(), dev=[]))
    assert snapshot(root) == before
