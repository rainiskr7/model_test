"""무엇: 역사 읽기 비변경·경로 경계 · 입력: 누락/손상 파일 · 출력: History · 계약 §5-1b."""

import pytest

from jeveval.io import history


def test_missing_history_is_read_only(tmp_path):
    result = history.read(tmp_path, "absent")
    assert not result.artifacts and not list(tmp_path.iterdir())
    assert all(s.expected is None for s in result.stages)


def test_history_outside_root_rejected(tmp_path):
    with pytest.raises(ValueError):
        history.read(tmp_path, "../outside")


def test_history_invalid_json_hides_original(tmp_path):
    (tmp_path / "fingerprint.json").write_text("PRIVATE_RAW")
    before = (tmp_path / "fingerprint.json").read_bytes()
    result = history.read(tmp_path, ".")
    assert result.errors == ["invalid_artifact"]
    assert (tmp_path / "fingerprint.json").read_bytes() == before
