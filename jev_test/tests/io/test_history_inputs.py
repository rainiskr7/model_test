"""무엇: 역사 재구성 입력 경계 · 입력: task 해시 · 출력: 차이 거부 · 계약 §5-1b."""

import pytest

from jeveval.io.history import read
from jeveval.io.history_inputs import checked_task
from tests.run.history_support import finished


def test_changed_task_refuses_reconstruction(tmp_path, monkeypatch):
    h = finished(tmp_path, monkeypatch)
    saved = read(tmp_path, h.directory)
    assert checked_task(tmp_path, saved) == "configs/tasks/klue_mrc_answerable.yaml"
    (tmp_path / "configs/tasks/klue_mrc_answerable.yaml").write_text("PRIVATE_RAW")
    with pytest.raises(ValueError):
        checked_task(tmp_path, saved)
