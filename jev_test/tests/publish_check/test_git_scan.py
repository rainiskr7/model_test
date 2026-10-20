"""무엇: 이력 전체 tree·blob 재사용·실패 코드. 입력: 임시 Git 저장소와 합성 원문. 출력: 안전한 JSON."""

import json
from pathlib import Path
import subprocess

import pytest

from audits.publish_check import __main__ as cli
from audits.publish_check.git_objects import CatFile, forbidden, inventory
from audits.publish_check.scan import scan
from audits.publish_check.sources import Document


TEXT = "여기에만존재하는합성비공개표본문장입니다"


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL).decode().strip()


def commit(root):
    git(root, "add", ".")
    git(root, "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", "commit", "-qm", "fixture")
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    (root / "public.txt").write_text("safe", encoding="utf-8")
    base = commit(root)
    return root, base


def provider(root, length):
    yield "synthetic", [Document(TEXT, [("private-id", "text")])], dict(rows=1, windows=len(TEXT) - length + 1)


def test_old_blob_and_all_path_commit_references(repository, tmp_path):
    root, base = repository
    (root / "gone.json").write_text(json.dumps({"text": TEXT}), encoding="utf-8")
    (root / "alias.json").write_bytes((root / "gone.json").read_bytes())
    first = commit(root)
    (root / "gone.json").unlink()
    (root / "unrelated.txt").write_text("also safe")
    last = commit(root)
    result = scan(root, base, last, source_provider=provider, scratch=tmp_path)
    hit = next(r for r in result["blobs"] if r["matches"])
    assert hit["commit_count"] == 2 and len(hit["references"]) == 3
    assert {"alias.json", "gone.json"} == set(hit["paths"])
    assert any(r["commit"] == first and r["path"] == "gone.json" for r in hit["references"])
    assert result["counts"]["failed_blobs"] == 0 and not result["ok"]
    assert TEXT not in json.dumps(result, ensure_ascii=False)
    assert "\\uc5ec" not in json.dumps(result)  # no escaped source either
    assert not list(tmp_path.glob("publish-check-*"))


@pytest.mark.parametrize("payload,max_bytes", [(b"\xff\x00", 1024), (b"long safe text", 2)])
def test_failed_blob_nonzero_cli_and_no_raw_output(repository, tmp_path, monkeypatch, capsys, payload, max_bytes):
    root, base = repository
    (root / "bad.bin").write_bytes(payload)
    last = commit(root)
    original = cli.scan
    monkeypatch.setattr(cli, "scan", lambda *a, **kw: original(*a, source_provider=provider, **kw))
    out = tmp_path / "report.json"
    assert cli.main(["--root", str(root), "--base", base, "--head", last, "--out", str(out),
                     "--max-blob-bytes", str(max_bytes)]) == 1
    result = json.loads(out.read_text())
    assert result["counts"]["failed_blobs"] > 0
    assert TEXT not in capsys.readouterr().out + out.read_text()


def test_clean_cli_and_output_must_be_new_outside_repo(repository, tmp_path, monkeypatch):
    root, base = repository
    (root / "safe.txt").write_text("safe enough")
    last = commit(root)
    original = cli.scan
    monkeypatch.setattr(cli, "scan", lambda *a, **kw: original(*a, source_provider=provider, **kw))
    args = ["--root", str(root), "--base", base, "--head", last]
    assert cli.main([*args, "--out", str(root / "report.json")]) == 2
    out = tmp_path / "report.json"
    assert cli.main([*args, "--out", str(out)]) == 0
    before = out.read_bytes()
    assert cli.main([*args, "--out", str(out)]) == 2
    assert out.read_bytes() == before


def test_source_failure_and_empty_range_are_not_success(repository, tmp_path):
    root, base = repository
    with pytest.raises(ValueError, match="empty commit range"):
        scan(root, base, base, source_provider=provider, scratch=tmp_path)
    (root / "safe.txt").write_text("safe")
    last = commit(root)
    def broken(root, length):
        raise ValueError(TEXT)
        yield
    result = scan(root, base, last, source_provider=broken, scratch=tmp_path)
    assert not result["ok"] and result["source_failures"]
    assert result["counts"]["checked_blobs"] == 0
    assert TEXT not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize("path", [
    "jev_test/results/a/attempts.jsonl", "final.jsonl", "dataset/example", "x/.work/log", ".env",
    "archive/run.tar.zst", *[f"jev_test/results/_t0/model/r/{n}.jsonl" for n in ("inputs", "reference", "server", "variants")],
])
def test_forbidden_paths(path):
    assert forbidden(path)
    assert not forbidden("tests/fixtures/input.json")


def test_forbidden_path_in_deleted_history(repository, tmp_path):
    root, base = repository
    directory = root / "dataset"
    directory.mkdir()
    path = directory / "synthetic.txt"
    path.write_text("safe short")
    first = commit(root)
    path.unlink()
    last = commit(root)
    result = scan(root, base, last, source_provider=provider, scratch=tmp_path)
    assert result["forbidden_paths"] == [dict(commit=first, path="dataset/synthetic.txt")]
    assert not result["ok"]


@pytest.mark.parametrize("copy_public", [False, True])
@pytest.mark.parametrize("add_new", [False, True])
def test_public_blob_skipped_and_new_blob_checked(repository, tmp_path, monkeypatch, copy_public, add_new):
    root, _ = repository
    (root / "published.txt").write_text(TEXT, encoding="utf-8")
    (root / "published.bin").write_bytes(b"\xff\x00")
    base = commit(root)
    public_oids = {git(root, "rev-parse", f"{base}:{path}")
                   for path in ("public.txt", "published.txt", "published.bin")}
    if copy_public:
        (root / "copy.json").write_text(TEXT, encoding="utf-8")
    if add_new:
        (root / "new.txt").write_text(TEXT + "새내용", encoding="utf-8")
    git(root, "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
        "commit", "--allow-empty", "-qm", "extra tree")
    head = commit(root) if copy_public or add_new else git(root, "rev-parse", "HEAD")
    read_oids = []
    original = CatFile.read

    def read(reader, oid, max_bytes):
        read_oids.append(oid)
        assert oid not in public_oids
        return original(reader, oid, max_bytes)

    monkeypatch.setattr(CatFile, "read", read)
    result = scan(root, base, head, source_provider=provider, scratch=tmp_path)
    assert result["counts"]["already_public_blobs"] == 3
    assert result["counts"]["total_blobs"] == int(add_new)
    assert result["counts"]["checked_blobs"] == int(add_new)
    assert result["counts"]["failed_blobs"] == 0
    assert bool(result["counts"]["match_intervals"]) == add_new
    assert result["ok"] == (not add_new)
    assert len(read_oids) == len(result["blobs"]) == int(add_new)
    assert public_oids.isdisjoint(row["oid"] for row in result["blobs"])
    if add_new:
        assert result["blobs"][0]["paths"] == ["new.txt"]
        assert result["blobs"][0]["matches"]


def test_blob_from_base_ancestor_is_already_public(repository, tmp_path):
    root, _ = repository
    (root / "old.txt").write_text(TEXT, encoding="utf-8")
    commit(root)
    (root / "old.txt").unlink()
    base = commit(root)
    (root / "restored.txt").write_text(TEXT, encoding="utf-8")
    head = commit(root)
    result = scan(root, base, head, source_provider=provider, scratch=tmp_path)
    assert result["counts"]["already_public_blobs"] == 2
    assert result["counts"]["total_blobs"] == 0
    assert result["blobs"] == [] and result["ok"]


def test_forbidden_path_in_base_still_reported(repository, tmp_path):
    root, _ = repository
    (root / ".env").write_text(TEXT, encoding="utf-8")
    base = commit(root)
    (root / "safe.txt").write_text("new safe text", encoding="utf-8")
    first = commit(root)
    (root / ".env").unlink()
    head = commit(root)
    result = scan(root, base, head, source_provider=provider, scratch=tmp_path)
    assert result["forbidden_paths"] == [dict(commit=first, path=".env")]
    assert result["counts"]["already_public_blobs"] == 2
    assert result["counts"]["total_blobs"] == 1
    assert result["counts"]["match_intervals"] == 0
    assert not result["ok"]


def test_unsupported_entry_in_base_still_reported(repository, tmp_path):
    root, original_base = repository
    git(root, "update-index", "--add", "--cacheinfo", f"160000,{original_base},module")
    git(root, "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
        "commit", "-qm", "gitlink")
    base = git(root, "rev-parse", "HEAD")
    git(root, "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
        "commit", "--allow-empty", "-qm", "same tree")
    head = git(root, "rev-parse", "HEAD")
    result = scan(root, base, head, source_provider=provider, scratch=tmp_path)
    assert result["unsupported_entries"] == [dict(commit=head, path="module", kind="commit")]
    assert not result["ok"]
