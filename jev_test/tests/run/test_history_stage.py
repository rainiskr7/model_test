"""무엇: 역사 단계 재구성 호출 해시 · 입력: 완료 run·변조 · 출력: 일치/거부 · 계약 §5-1b."""

import pytest

from jeveval.io.history import read
from jeveval.run.history_stage import restore
from tests.run.history_support import finished


def test_reconstruction_checks_actual_request_hash(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    assert len(restore(tmp_path, read(tmp_path, h.directory), "test").items) == 1
    path = h.directory / "test/final.jsonl"
    text = path.read_text()
    import json
    value = json.loads(text)
    value["calls"][0]["request_sha256"] = "a" * 64
    path.write_text(json.dumps(value) + "\n")
    with pytest.raises(ValueError, match="request bytes"):
        restore(tmp_path, read(tmp_path, h.directory), "test")
