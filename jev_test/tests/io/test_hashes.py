"""무엇: 해시 목록 대조 · 입력: 임시 합성 파일 · 출력: 해시·불일치 · 계약 §5-6·§8-6."""

import hashlib

import pytest

from jeveval.io.hashes import code_sha256, read_sha256sums, sha256_file, tokenizer_sha256, verify_dir


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


def test_code_hash_relative_paths_sorted_and_cache_excluded(tmp_path):
    code = tmp_path / "jeveval"
    (code / "__pycache__").mkdir(parents=True)
    (code / "z.py").write_bytes(b"z")
    (code / "a.py").write_bytes(b"a")
    (code / "__pycache__/ignored.py").write_bytes(b"ignored")
    (code / "not_python.json").write_bytes(b"ignored")
    assert code_sha256(tmp_path) == hashlib.sha256(b"jeveval/a.py\0ajeveval/z.py\0z").hexdigest()


def test_tokenizer_symlink_escape_is_rejected(tmp_path):
    root = tmp_path / "tok"
    root.mkdir()
    target = tmp_path / "outside"
    target.write_text("same hash but outside")
    (root / "tokenizer.json").symlink_to(target)
    with pytest.raises(ValueError, match="outside"):
        tokenizer_sha256(root, {"tokenizer.json": sha256_file(target)})
