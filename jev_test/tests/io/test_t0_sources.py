"""무엇: T0 공개 원본 읽기 경계 · 입력: 셋/경로 설정 · 출력: 제한 전 검사 · 계약 §8-7 T-c."""

from types import SimpleNamespace

import pytest

from jeveval.io import t0_sources
from jeveval.types import SourceRow
from jeveval.types.set_config import SetEntry


def fake_catalog(rules):
    return [SetEntry(n, c.get("family", n), {"id": n}, c, None, ()) for n, c in rules["sets"].items()]


@pytest.mark.parametrize("name", ["fc_call_decision", "143.private", "unknown"])
def test_forbidden_set_never_calls_reader(tmp_path, monkeypatch, name):
    monkeypatch.setattr(t0_sources, "read_yaml", lambda p: {"sets":{}, "seed":42})
    monkeypatch.setattr(t0_sources, "read_set_rows", lambda *a, **kw: pytest.fail("forbidden reader called"))
    with pytest.raises(ValueError, match="forbidden"):
        t0_sources.read_sources(tmp_path, [name])


@pytest.mark.parametrize("path", ["dataset/143.private/data.json", "../outside/data.json"])
def test_public_name_cannot_redirect_reader(tmp_path, monkeypatch, path):
    rules = dict(seed=42, sets={"kmhas":dict(source=dict(file=path), group_key="text")})
    monkeypatch.setattr(t0_sources, "read_yaml", lambda p: rules)
    monkeypatch.setattr(t0_sources, "catalog", lambda root: fake_catalog(rules))
    monkeypatch.setattr(t0_sources, "read_set_rows", lambda *a, **kw: pytest.fail("redirected reader called"))
    with pytest.raises(ValueError, match="outside public set"):
        t0_sources.read_sources(tmp_path, ["kmhas"])


def test_public_rows_grouped_before_pool_check(tmp_path, monkeypatch):
    rules = dict(seed=42, sets={"kmhas":dict(source=dict(file="dataset/kmhas/part1.parquet"), group_key="text")})
    rows = [SourceRow("kmhas", "0", {"text":"same"}), SourceRow("kmhas", "1", {"text":"same"})]
    monkeypatch.setattr(t0_sources, "read_yaml", lambda p: rules)
    monkeypatch.setattr(t0_sources, "catalog", lambda root: fake_catalog(rules))
    monkeypatch.setattr(t0_sources, "read_set_rows", lambda *a, **kw: rows)
    monkeypatch.setattr(t0_sources, "read_split_plan", lambda p: SimpleNamespace(groups={"0":[]}))
    sources = t0_sources.read_sources(tmp_path, ["kmhas"])
    assert sources.groups["kmhas"].row_to_group == {"0":"0", "1":"0"}
    assert sources.pools["kmhas"] == {"0"}


def test_same_family_pool_union_even_when_only_one_alias_selected(tmp_path, monkeypatch):
    rules = dict(seed=42, sets={name: dict(family="kosgd", source=dict(dir=f"dataset/{name}"), group_key="dialogue_id")
                              for name in ("kosgd", "kosgd2")})
    monkeypatch.setattr(t0_sources, "read_yaml", lambda p: rules)
    monkeypatch.setattr(t0_sources, "catalog", lambda root: fake_catalog(rules))
    monkeypatch.setattr(t0_sources, "read_set_rows", lambda *args, **kw: [SourceRow("kosgd2", "d#0", {"dialogue_id": "d", "turn_index": 0})])
    monkeypatch.setattr(t0_sources, "read_split_plan", lambda p: SimpleNamespace(groups={"old" if p.stem == "kosgd" else "new": []}))
    result = t0_sources.read_sources(tmp_path, ["kosgd2"])
    assert result.pools["kosgd2"] == {"old", "new"} and result.families["kosgd2"] == "kosgd"
