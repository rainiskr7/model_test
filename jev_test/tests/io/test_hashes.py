"""무엇: 해시 목록 대조 · 입력: 임시 합성 파일 · 출력: 해시·불일치 · 계약 §5-6·§8-6."""

import hashlib

import pytest

from jeveval.io.hashes import read_sha256sums, sha256_file, verify_dir


def test_streaming_hash_and_verification(tmp_path):
    body = b"synthetic\x00" * 250000
    (tmp_path / "ok.bin").write_bytes(body)
    expected = hashlib.sha256(body).hexdigest()
    assert sha256_file(tmp_path / "ok.bin") == expected
    (tmp_path / "wrong").write_text("changed")
    (tmp_path / "unlisted").write_text("ignored")
    manifest = tmp_path / "SHA256SUMS"
    manifest.write_text(f"{expected.upper()}  ok.bin\n" + "0" * 64 + "  wrong\n"
                        + "0" * 64 + "  missing\n" + "0" * 64 + "  SHA256SUMS\n")
    assert read_sha256sums(manifest)["ok.bin"] == expected
    assert verify_dir(tmp_path) == ["wrong", "missing"]


@pytest.mark.parametrize("line", ["", "a" * 63 + "  f", "g" * 64 + "  f", "a" * 64 + " f",
                                     "a" * 64 + "  ", "a" * 64 + "  ../f", "a" * 64 + "  /f"])
def test_invalid_manifest(tmp_path, line):
    path = tmp_path / "SHA256SUMS"
    path.write_text(line + "\n")
    with pytest.raises(ValueError):
        read_sha256sums(path)


def test_duplicate_nested_and_space_names(tmp_path):
    path = tmp_path / "SHA256SUMS"
    line = "a" * 64 + "  dir/file name\n"
    path.write_text(line)
    assert read_sha256sums(path) == {"dir/file name": "a" * 64}
    path.write_text(line * 2)
    with pytest.raises(ValueError, match="duplicate"):
        read_sha256sums(path)


def test_missing_manifest_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        verify_dir(tmp_path)
