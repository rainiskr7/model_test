"""무엇: 주판 소유 경계 · 입력: 합성 task·overlay · 출력: unrelated task 격리 · 계약 판 5 보정 1 §9."""

from dataclasses import replace

import pytest

from jeveval.io.set_config import entry
from jeveval.io.set_tasks import primary_variant, require_task
from tests.run.cli_support import Harness


def test_primary_ignores_unowned_invalid_or_conflicting_tasks(tmp_path):
    h = Harness(tmp_path)
    selected = entry(tmp_path, h.set)
    original = tmp_path / selected.task_files[0]
    (tmp_path / "configs/tasks/foreign.yaml").write_text(original.read_text().replace("variant: default", "variant: other"))
    assert primary_variant(tmp_path, selected) == "default"
    (tmp_path / "configs/tasks/foreign.yaml").write_text("broken: [")
    assert primary_variant(tmp_path, selected) == "default"
    (tmp_path / "configs/tasks/foreign.yaml").unlink()
    assert primary_variant(tmp_path, selected) == "default"
    original.write_text(original.read_text().replace("set: klue_mrc_answerable", "set: other"))
    with pytest.raises(ValueError, match="ownership"):
        primary_variant(tmp_path, selected)


def test_alias_primary_and_task_ownership(tmp_path):
    h = Harness(tmp_path, "kosgd2", "full")
    selected = entry(tmp_path, h.set)
    assert primary_variant(tmp_path, selected) == "full"
    require_task(tmp_path, selected, selected.task_files[0])
    with pytest.raises(ValueError, match="not declared"):
        require_task(tmp_path, selected, "configs/tasks/kosgd_full.yaml")
    with pytest.raises(ValueError, match="SPEC_AMBIGUOUS"):
        primary_variant(tmp_path, replace(selected, dataset={}, task_files=()))
