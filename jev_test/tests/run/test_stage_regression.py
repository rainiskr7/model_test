"""무엇: 역사·단계 고정 회귀 · 입력: d41e8b9 합성 관측 · 출력: 현행 결과 동치 · 계약 §9 C6."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from jeveval.io import history
from jeveval.run import history_check
from tests.run.stage_regression_support import observed


@pytest.mark.parametrize("name", ["fc_call_decision", "klue_mrc_answerable"])
def test_history_report_score_archive_compare_keep_baseline(tmp_path, monkeypatch, name):
    """정상 완료 run의 단계·판정·분모를 변경 전 코드에서 만든 고정값과 대조한다."""
    expected = json.loads(Path(__file__).with_name("stage_d41e8b9.json").read_text())
    h, actual = observed(tmp_path, monkeypatch, name)
    assert actual == expected[name]
    before = deepcopy(history_check.check(history.read(tmp_path, h.directory)))
    # 역사 집계는 현재 rules의 누락/손상을 읽지 않는다. 새로운 설정 의존성도 금지한다.
    rules = tmp_path / "configs/splits/rules.yaml"
    rules.write_text("sets: [malformed")
    assert history_check.check(history.read(tmp_path, h.directory)) == before
    rules.unlink()
    assert history_check.check(history.read(tmp_path, h.directory)) == before
