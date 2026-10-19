"""무엇: 보고 입출력 경로 · 입력: 출력/명시 비교 · 출력: 탈출 거부 · 계약 §7-6."""

import pytest

from jeveval.io.report_inputs import compare, output


def test_compare_exact_id_and_dedicated_markdown_path(tmp_path):
    assert compare(tmp_path, "results", "c", "s", "v") is None
    assert output(tmp_path, "report.md") == tmp_path / "report.md"
    for path in ("../outside.md", "fingerprint.json", "P1_CONTRACT.md"):
        with pytest.raises(ValueError):
            output(tmp_path, path)


def test_symlink_output_escape_rejected(tmp_path):
    root, outside = tmp_path / "repo", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        output(root, "link/report.md")
