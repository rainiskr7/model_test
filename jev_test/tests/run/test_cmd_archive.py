"""무엇: run_id 완료 보존/누출 · 입력: 두 모델 canary 실행 · 출력: 실제 archive/커밋 집계 · 계약 ⑥b-2 R8."""

import tarfile
from types import SimpleNamespace

import pytest
import zstandard

from jeveval.io import run_files
from jeveval.io.archive import verify_archive
from jeveval.run import cli, cmd_archive
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


@pytest.fixture
def archive_unit(tmp_path, monkeypatch):
    """명령 자체를 실행하고 I/O 경계의 호출·쓰기 순서를 관측한다."""
    events, contexts = [], []
    for model in ("first", "second"):
        directory = tmp_path / "results" / model / "r1/A/set/default"
        contexts.append(SimpleNamespace(directory=directory, cfg=SimpleNamespace(id=model),
            task=SimpleNamespace(set="set", variant="default"), fingerprint={"run_id": "r1"}))
    def completed(root, directory):
        events.append(("completed", directory))
        ctx = next(c for c in contexts if c.directory == directory)
        return ctx, {"test": SimpleNamespace(warnings=[ctx.cfg.id])}, None
    def entries(root, values):
        events.append(("entries", [c.directory for c in values]))
        return {"synthetic": tmp_path / "input"}
    def build(values, path):
        events.append(("build", path))
        return {"sha256": "a" * 64, "nbytes": 1, "files": list(values)}
    monkeypatch.setattr(cmd_archive.archive, "run_directories", lambda *a: [c.directory for c in contexts])
    monkeypatch.setattr(cmd_archive.context, "completed", completed)
    monkeypatch.setattr(cmd_archive.run_files, "read_json", lambda p: {"file": p.name})
    monkeypatch.setattr(cmd_archive.context, "check_identity",
                        lambda c, data: events.append(("identity", c.directory, data["file"])))
    monkeypatch.setattr(cmd_archive.archive, "entries_for", entries)
    monkeypatch.setattr(cmd_archive.archive, "build_archive", build)
    monkeypatch.setattr(cmd_archive.run_files, "make_directory", lambda p: events.append(("mkdir", p)))
    monkeypatch.setattr(cmd_archive.run_files, "write_json", lambda p, v: events.append(("write", p, dict(v))))
    return contexts, events


@pytest.mark.parametrize("obstacle", ["no_runs", "archive", "metadata"])
def test_direct_archive_refuses_missing_or_archived_runs(tmp_path, monkeypatch, archive_unit, obstacle):
    contexts, events = archive_unit
    if obstacle == "no_runs":
        contexts.clear()
    else:
        existing = (tmp_path / "archive/r1.tar.zst" if obstacle == "archive"
                    else contexts[-1].directory / "archive.json")
        monkeypatch.setattr(cmd_archive.run_files, "exists", lambda p: p == existing)
    with pytest.raises(ValueError, match="^missing runs or already archived$"):
        cmd_archive.run(root=tmp_path, run_id="r1")
    assert events == []


@pytest.mark.parametrize("field", ["run_id", "directory"])
def test_direct_archive_rejects_identity_before_writes(tmp_path, archive_unit, field):
    contexts, events = archive_unit
    if field == "run_id":
        contexts[0].fingerprint["run_id"] = "other"
    else:
        contexts[0].cfg.id = "other"
    with pytest.raises(ValueError, match="^archive run identity differs$"):
        cmd_archive.run(root=tmp_path, run_id="r1")
    assert events == [("completed", contexts[0].directory)]


def test_direct_archive_writes_metadata_after_build(tmp_path, archive_unit):
    contexts, events = archive_unit
    assert cmd_archive.run(root=tmp_path, run_id="r1") == {"ok": True, "warnings": ["first", "second"]}
    assert [e[0] for e in events] == ["completed", "identity", "identity"] * 2 + [
        "entries", "mkdir", "build", "write", "write"]
    assert events[1:3] == [("identity", contexts[0].directory, name) for name in ("scores.json", "risk.json")]
    assert events[-3] == ("build", tmp_path / "archive/r1.tar.zst")
    metadata = {"sha256": "a" * 64, "nbytes": 1, "files": ["synthetic"], "archive": "archive/r1.tar.zst"}
    assert events[-2:] == [("write", ctx.directory / "archive.json", metadata) for ctx in contexts]


def test_direct_archive_build_failure_writes_no_metadata(tmp_path, monkeypatch, archive_unit):
    _, events = archive_unit
    def fail(*args):
        events.append(("build_failed",))
        raise OSError("synthetic archive failure")
    monkeypatch.setattr(cmd_archive.archive, "build_archive", fail)
    with pytest.raises(OSError, match="^synthetic archive failure$"):
        cmd_archive.run(root=tmp_path, run_id="r1")
    assert events[-1] == ("build_failed",) and not any(e[0] == "write" for e in events)
