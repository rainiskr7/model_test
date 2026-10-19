import pytest

from tools.output_baseline.boundary import safe_output


def test_protected_output_and_symlink_rejected(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "data", target_is_directory=True)
    for name in ("results/manifest.json", "data/out", "configs/out", "link/out"):
        with pytest.raises(ValueError, match="outside"):
            safe_output(tmp_path, tmp_path / name)
    assert safe_output(tmp_path, tmp_path / "out") == tmp_path / "out"
