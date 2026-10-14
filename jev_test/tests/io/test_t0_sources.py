"""무엇: T0 공개 원본 읽기 경계 · 입력: 셋/경로 설정 · 출력: 제한 전 검사 · 계약 §8-7 T-c."""

from types import SimpleNamespace

import pytest

from jeveval.io import t0_sources
from jeveval.types import SourceRow


@pytest.mark.parametrize("name", ["fc_call_decision", "143.private", "unknown"])
def test_forbidden_set_never_calls_reader(tmp_path, monkeypatch, name):
    monkeypatch.setattr(t0_sources, "read_yaml", lambda p: {"sets":{}, "seed":42})
    monkeypatch.setattr(t0_sources, "read_set_rows", lambda *a: pytest.fail("forbidden reader called"))
    with pytest.raises(ValueError, match="forbidden"):
        t0_sources.read_sources(tmp_path, [name])


@pytest.mark.parametrize("path", ["dataset/143.private/data.json", "../outside/data.json"])
def test_public_name_cannot_redirect_reader(tmp_path, monkeypatch, path):
    rules = dict(seed=42, sets={"kmhas":dict(source=dict(file=path), group_key="text")})
    monkeypatch.setattr(t0_sources, "read_yaml", lambda p: rules)
    monkeypatch.setattr(t0_sources, "read_set_rows", lambda *a: pytest.fail("redirected reader called"))
    with pytest.raises(ValueError, match="outside public set"):
        t0_sources.read_sources(tmp_path, ["kmhas"])


def test_public_rows_grouped_before_pool_check(tmp_path, monkeypatch):
    rules = dict(seed=42, sets={"kmhas":dict(source=dict(file="dataset/kmhas/part1.parquet"), group_key="text")})
    rows = [SourceRow("kmhas", "0", {"text":"same"}), SourceRow("kmhas", "1", {"text":"same"})]
    monkeypatch.setattr(t0_sources, "read_yaml", lambda p: rules)
    monkeypatch.setattr(t0_sources, "read_set_rows", lambda *a: rows)
    monkeypatch.setattr(t0_sources, "read_split_plan", lambda p: SimpleNamespace(groups={"0":[]}))
    sources = t0_sources.read_sources(tmp_path, ["kmhas"])
    assert sources.groups["kmhas"].row_to_group == {"0":"0", "1":"0"}
    assert sources.pools["kmhas"] == {"0"}
