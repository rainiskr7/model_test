"""무엇: reader 선택 경계 · 입력: 셋과 설정 · 출력: 선택된 reader 인자/거부 · 계약 §6·§8-1."""

import pytest

from jeveval.io import sources
from jeveval.types import SourceRow


def test_unknown_set_rejected_before_reader(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("unknown set reached a reader")
    for reader in sources.READERS.values():
        monkeypatch.setattr(reader, "read_rows", forbidden)
    with pytest.raises(ValueError, match="^unknown set: unknown$"):
        sources.read_set_rows("unknown", {}, tmp_path)


@pytest.mark.parametrize("set_name", sorted(sources.READERS))
def test_only_kote_receives_votes_config(monkeypatch, tmp_path, set_name):
    config = {"source": {"file": "synthetic"}, "votes": {"n_raters": 5}}
    expected = [SourceRow(set_name, "1", {})]
    calls = []
    def read(source, root, **kwargs):
        calls.append((source, root, kwargs))
        return expected
    monkeypatch.setattr(sources.READERS[set_name], "read_rows", read)
    result = sources.read_set_rows(set_name, config, tmp_path)
    assert result is expected
    assert calls == [(config["source"], tmp_path,
                      {"votes_cfg": config["votes"]} if set_name == "kote_escalation" else {})]
