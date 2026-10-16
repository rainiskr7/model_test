"""무엇: T0 참조 길이 필수 경계 · 입력: Clef 계열/누락·잘못된 길이 · 출력: 로딩 전 거부 · 계약 §8-6 H·I."""

import pytest

from jeveval.reference import t0_runner


@pytest.mark.parametrize("family", ["clef", "clef_flash"])
@pytest.mark.parametrize("options", [{}, {"max_length": None}, {"max_length": 0},
    {"max_length": -1}, {"max_length": True}, {"max_length": 1.5}])
def test_clef_load_requires_positive_max_length(tmp_path, monkeypatch, family, options):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid limit reached the model loader")

    monkeypatch.setattr(t0_runner.clef_runner, "load", forbidden)
    with pytest.raises(ValueError, match="^max_length is required for Clef references$"):
        t0_runner.load(family, tmp_path, **options)
