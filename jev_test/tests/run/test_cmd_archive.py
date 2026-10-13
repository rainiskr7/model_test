"""무엇: run_id 완료 보존/누출 · 입력: 두 모델 canary 실행 · 출력: 실제 archive/커밋 집계 · 계약 ⑥b-2 R8."""

import tarfile

import pytest
import zstandard

from jeveval.io import run_files
from jeveval.io.archive import verify_archive
from jeveval.run import cli
from tests.run.cli_support import output_files
from tests.run.compare_support import pair
from tests.run.test_cmd_compare import compare, result


def test_real_archive_compare_canary_positive_control(tmp_path, monkeypatch):
    h, other = pair(tmp_path, monkeypatch)
    markers = [h.markers[key] for key in ("state", "group")]
    for model in (h, other):
        private = (model.directory / "test/attempts.jsonl").read_text()
        assert all(marker in private for marker in markers)
    assert compare(h, other) == 0
    assert cli.main(["compare", "--run-dirs", str(h.directory), str(other.directory), "--compare-id", "r1"]) == 0
    assert result(h)["common_cohort"]["n"] == 1
    assert cli.main(["archive", "--run-id", "r1"]) == 0
    archive = tmp_path / "archive/r1.tar.zst"
    assert archive.is_file()
    manifests = [run_files.read_json(x.directory / "archive.json") for x in (h, other)]
    assert manifests[0] == manifests[1]
    assert manifests[0]["archive"] == "archive/r1.tar.zst"
    assert verify_archive(archive, manifests[0]) == []
    files = manifests[0]["files"]
    assert files == sorted(files)
    assert {"configs/datasets.yaml", "configs/splits/rules.yaml"} <= set(files)
    for model in (h, other):
        prefix = model.directory.relative_to(tmp_path).as_posix()
        assert {f"{prefix}/fingerprint.json", f"{prefix}/test/attempts.jsonl"} <= set(files)
        fp = run_files.read_json(model.directory / "fingerprint.json")
        assert set(fp["files"]) <= set(files)
    with archive.open("rb") as raw, zstandard.ZstdDecompressor().stream_reader(raw) as stream:
        with tarfile.open(fileobj=stream, mode="r|") as tar:
            payloads = [tar.extractfile(member).read().decode() for member in tar if member.name.endswith("attempts.jsonl")]
    assert all(any(marker in payload for payload in payloads) for marker in markers)
    committed = ["fingerprint.json", "threshold.json", "test/seal.json", "scores.json", "risk.json", "summary.json", "archive.json"]
    public = [x.directory / name for x in (h, other) for name in committed]
    public += list((tmp_path / "results/_compare").rglob("compare.json"))
    assert len(public) == 16
    for path in public:
        assert all(marker not in path.read_text() for marker in markers + ["private-test-key"])
    before = output_files(tmp_path)
    assert cli.main(["archive", "--run-id", "r1", "--archive-root", "another"]) == 1
    assert output_files(tmp_path) == before


@pytest.mark.parametrize("missing", ["dev/final.jsonl", "test/final.jsonl", "extra/final.jsonl",
                                     "threshold.json", "test/seal.json", "scores.json", "risk.json", "fingerprint.json"])
def test_archive_refuses_any_incomplete_run_before_write(tmp_path, monkeypatch, missing):
    h, other = pair(tmp_path, monkeypatch, "fc_call_decision")
    (other.directory / missing).unlink()
    before = output_files(tmp_path)
    assert cli.main(["archive", "--run-id", "r1"]) == 1
    assert output_files(tmp_path) == before


@pytest.mark.parametrize("obstacle", ["destination", "metadata", "empty_run", "missing_attempts"])
def test_archive_existing_or_unfinished_refused(tmp_path, monkeypatch, obstacle):
    h, other = pair(tmp_path, monkeypatch)
    if obstacle == "destination":
        (tmp_path / "archive").mkdir()
        (tmp_path / "archive/r1.tar.zst").write_bytes(b"existing")
    elif obstacle == "metadata":
        (other.directory / "archive.json").write_text("{}")
    elif obstacle == "missing_attempts":
        (other.directory / "test/attempts.jsonl").unlink()
    else:
        (tmp_path / "results/third/r1/A/set/default").mkdir(parents=True)
    before = output_files(tmp_path)
    assert cli.main(["archive", "--run-id", "r1"]) == 1
    assert output_files(tmp_path) == before


def test_functionchat_archive_contains_all_stages(tmp_path, monkeypatch):
    h, other = pair(tmp_path, monkeypatch, "fc_call_decision")
    assert cli.main(["archive", "--run-id", "r1"]) == 0
    metadata = run_files.read_json(h.directory / "archive.json")
    for model in (h, other):
        prefix = model.directory.relative_to(tmp_path).as_posix()
        assert {f"{prefix}/{stage}/{name}.jsonl" for stage in ("dev", "test", "extra")
                for name in ("attempts", "final")} <= set(metadata["files"])
