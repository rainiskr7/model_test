"""무엇: 결과 경로 경계 · 입력: 식별자·임시 경로 · 출력: 경로 제한 · 계약 §5-1·§8-1."""

import pytest

from jeveval.run.layout import compare_dir, run_dir


@pytest.mark.parametrize("bad", [".", "..", "_compare", "a/b", "/absolute", "a\\b", "", "a b"])
def test_invalid_identifiers(tmp_path, bad):
    for values in ((bad, "r1", "set", "full"), ("model", bad, "set", "full"),
                   ("model", "r1", bad, "full"), ("model", "r1", "set", bad)):
        with pytest.raises(ValueError):
            run_dir(tmp_path, *values)
    with pytest.raises(ValueError):
        compare_dir(tmp_path, bad, "set", "full")


def test_paths_and_symlink_escape(tmp_path):
    root = tmp_path / "results"
    root.mkdir()
    assert run_dir(root, "model", "r1", "set", "full") == root / "model/r1/A/set/full"
    assert compare_dir(root, "c1", "set", "full") == root / "_compare/c1/A/set/full"
    (root / "model").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        run_dir(root, "model", "r1", "set", "full")
