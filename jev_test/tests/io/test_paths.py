"""무엇: 공통 경로 경계 · 입력: 식별자·임시 경로 · 출력: 제한 경로/stat · 계약 §5-1·§8-1."""

import os

import pytest

from jeveval.io.paths import file_info, identifier, inside


@pytest.mark.parametrize("value", ["a", "Z", "0", "model-1", "run_20261017", "v1.2", "A_b-c.9"])
def test_identifier_accepts_path_components(value):
    assert identifier(value) == value


@pytest.mark.parametrize("value", ["", ".", "..", "_compare", "-run", "a/b", "a\\b",
                                  "/absolute", "a b", "a\n", "a\x00b", "모델"])
def test_identifier_rejects_invalid_strings(value):
    with pytest.raises(ValueError, match="^invalid result identifier$"):
        identifier(value)


@pytest.mark.parametrize("value", [None, True, 1, 1.5, b"run", [], {}])
def test_identifier_rejects_non_strings(value):
    with pytest.raises(ValueError, match="^invalid result identifier$"):
        identifier(value)


def test_inside_resolves_contained_relative_and_absolute_paths(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    expected = root.resolve() / "nested/file"
    assert inside(root, "nested/file") == expected
    assert inside(root, expected) == expected
    assert inside(root, "nested/../file") == root.resolve() / "file"
    assert inside(root, ".") == root.resolve()


@pytest.mark.parametrize("absolute", [False, True], ids=["parent-traversal", "absolute"])
def test_inside_rejects_paths_outside_root(tmp_path, absolute):
    root = tmp_path / "repository"
    root.mkdir()
    path = tmp_path / "outside" if absolute else "../outside"
    with pytest.raises(ValueError, match="^path outside repository$"):
        inside(root, path)


def test_inside_rejects_symlink_escape(tmp_path):
    root, outside = tmp_path / "repository", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="^path outside repository$"):
        inside(root, "link/file")


def test_file_info_returns_byte_size_and_mtime(tmp_path):
    path = tmp_path / "file"
    payload = "합성 파일\n".encode("utf-8")
    path.write_bytes(payload)
    stamp = 1_700_000_000
    os.utime(path, (stamp, stamp))
    assert file_info(path) == (len(payload), float(stamp))
