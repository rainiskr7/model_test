"""C7.1: real CLI with a fake client and saved artifacts in a disposable checkout.

KOFFVQA_COMPLETE_REVISION=3b5377e runs test_c71 with the same assertion (must fail).
"""

import json
import shutil

import pytest
from openpyxl import load_workbook

from shared.multimodal.tests.koffvqa_completion_support import Fixture, selected_revision


def test_c71_partial_judge_saves_artifacts_but_fails(tmp_path):
    fx = Fixture(tmp_path / "checkout", selected_revision())
    result = fx.judge(JUDGE_OUTCOME="partial")
    rows = json.loads((fx.judge_dir() / "results.json").read_text())
    summary = json.loads((fx.judge_dir() / "summary.json").read_text())
    assert (summary["total"], summary["scored"], summary["avg_score"]) == (2, 1, 8)
    assert len(rows) == 2 and rows[1]["error"] and rows[1]["score"] is None
    assert result.returncode == 10
    assert result.stderr == "[koffvqa_judge] incomplete: scored 1/2, rows=2\n"


@pytest.mark.parametrize("count,rc", [(0, 10), (2, 0)])
def test_judge_cli_empty_and_complete(tmp_path, count, rc):
    fx = Fixture(tmp_path / "checkout")
    result = fx.judge(count=count)
    assert result.returncode == rc
    assert (fx.judge_dir() / "results.json").is_file()
    assert (fx.judge_dir() / "summary.json").is_file()


def test_complete_judge_preserves_head_artifact_bytes(tmp_path):
    old = Fixture(tmp_path / "old", "3b5377e")
    new = Fixture(tmp_path / "new")
    assert old.judge().returncode == 0
    pred = "results/fixture_model/fixture_r1/vision/multimodal/koffvqa/model_gen.xlsx"
    (new.base / pred).parent.mkdir(parents=True)
    shutil.copyfile(old.base / pred, new.base / pred)
    assert new.judge().returncode == 0
    for name in ("results.json", "summary.json"):
        before = (old.judge_dir() / name).read_text().replace(str(old.base), "<BASE>")
        after = (new.judge_dir() / name).read_text().replace(str(new.base), "<BASE>")
        assert after == before


def test_invalid_key_and_columns_keep_existing_cli_codes(tmp_path):
    fx = Fixture(tmp_path / "checkout")
    assert fx.judge(FIXTURE_KEY="").returncode == 2
    assert not fx.judge_dir().exists()
    pred = fx.judge_dir().parent / "koffvqa/model_gen.xlsx"
    book = load_workbook(pred)
    book.active["C1"] = "missing_criteria"
    book.save(pred)
    book.close()
    assert fx.judge().returncode == 1
    assert not fx.judge_dir().exists()
