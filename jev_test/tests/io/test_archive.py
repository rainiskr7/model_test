"""무엇: 보존 바이트/검증 · 입력: 합성 파일 · 출력: 결정성/손상 거부 · 계약 ⑥b-2 R4–6."""

import os
import tarfile

import pytest
import zstandard

from jeveval.io.archive import build_archive, verify_archive


def test_archive_deterministic_despite_metadata_and_entry_order(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"private a")
    b.write_bytes(b"private b")
    first, second = tmp_path / "one.zst", tmp_path / "two.zst"
    manifest = build_archive({"b": b, "a": a}, first)
    for p in (a, b):
        os.utime(p, (123, 456))
        p.chmod(0o600)
        # 일반 계정이 변경 가능한 실제 소유권: 자신과 소속 그룹.
        os.chown(p, os.getuid(), os.getgroups()[0])
    assert build_archive({"a": a, "b": b}, second) == manifest
    assert first.read_bytes() == second.read_bytes()
    assert verify_archive(first, manifest) == []
    with first.open("rb") as raw, zstandard.ZstdDecompressor().stream_reader(raw) as stream:
        with tarfile.open(fileobj=stream, mode="r|") as archive:
            for info in archive:
                assert (info.mtime, info.uid, info.gid, info.uname, info.gname, info.mode) == (0, 0, 0, "", "", 0o644)
    with pytest.raises(FileExistsError):
        build_archive({"a": a}, first)


def test_archive_ignores_all_source_stat_fields(tmp_path, monkeypatch):
    source = tmp_path / "data"
    source.write_bytes(b"contents")
    first, second = tmp_path / "a.zst", tmp_path / "b.zst"
    build_archive({"data": source}, first)
    from pathlib import Path
    original = Path.stat
    def altered(path, *args, **kwargs):
        stat = original(path, *args, **kwargs)
        if path != source:
            return stat
        return os.stat_result((0o100777, stat.st_ino, stat.st_dev, stat.st_nlink,
                               12345, 54321, stat.st_size, 100, 200, 300))
    monkeypatch.setattr(Path, "stat", altered)
    build_archive({"data": source}, second)
    assert first.read_bytes() == second.read_bytes()


def test_verify_hash_names_size_and_corruption(tmp_path):
    source, output = tmp_path / "data", tmp_path / "out.zst"
    source.write_bytes(b"payload")
    manifest = build_archive({"data": source}, output)
    for key, bad in (("sha256", "0" * 64), ("nbytes", 0), ("files", ["wrong"])):
        assert verify_archive(output, {**manifest, key: bad}) == [key]
    output.write_bytes(b"invalid")
    assert "unreadable archive" in verify_archive(output, manifest)
    assert verify_archive(tmp_path / "absent", manifest)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../b", "./name", ""])
def test_unsafe_member_rejected_before_creation(tmp_path, name):
    with pytest.raises(ValueError):
        build_archive({name: tmp_path / "missing"}, tmp_path / "out.zst")
    assert not (tmp_path / "out.zst").exists()
