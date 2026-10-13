"""무엇: 집계 자료형 중첩 복원 · 입력: 합성 집계 · 출력: 검증 · 계약 §7-4~7-6·§8-5."""

import pytest

from jeveval.types import Population, QStats, ScoreTable, Threshold, ThresholdFile
from samples import score, threshold_file


def test_threshold_nested_and_key_matches_tau():
    original = threshold_file()
    source = original.to_dict()
    restored = ThresholdFile.from_dict(source)
    assert isinstance(restored.by_tau['0.02'], Threshold)
    source['by_tau']['0.02']['coverage']['num'] = 0
    assert restored == original
    source['by_tau']['0.02']['tau'] = '0.05'
    with pytest.raises(ValueError,match='key must equal'):
        ThresholdFile.from_dict(source)


def test_population_questions_and_pooled_rebuilt():
    original = score()
    source = original.to_dict()
    restored = ScoreTable.from_dict(source)
    pop = restored.populations['test']
    assert isinstance(pop, Population)
    assert isinstance(pop.questions['aspect_1'], QStats)
    assert isinstance(pop.pooled['aspect'], QStats)
    source['populations']['test']['pooled']['aspect']['calibration']['bins'][0]['n'] = 9
    assert restored == original


def test_unknown_score_field():
    with pytest.raises(ValueError,match='unknown fields'):
        ScoreTable.from_dict({'accuracy':.5})
