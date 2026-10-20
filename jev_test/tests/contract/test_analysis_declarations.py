"""무엇: 다중 선언 정규화 · 입력: 구 문자열/매핑 · 출력: 종류·경로 거부 · 계약 §7-4d."""

import pytest
from jeveval.contract.analysis_declarations import normalize_declarations
from jeveval.io.config import read_yaml, DuplicateKeyError


def test_legacy_mapping_and_no_declaration():
    path = 'configs/analysis/question_risk_v2.yaml'
    assert normalize_declarations(path) == normalize_declarations({'question_risk': path})
    assert normalize_declarations(None) == {}


@pytest.mark.parametrize('value', [[], {}, {'unknown': 'configs/analysis/a.yaml'},
    {'question_risk': '../a.yaml'}, {'question_risk': 'configs/analysis/a.yaml', 'score_variants': 'configs/analysis/a.yaml'}])
def test_bad_declarations(value):
    with pytest.raises(ValueError): normalize_declarations(value)


def test_yaml_duplicate_kind_is_rejected(tmp_path):
    path = tmp_path / 'policy.yaml'
    path.write_text('analysis:\n  question_risk: a\n  question_risk: b\n')
    with pytest.raises(DuplicateKeyError): read_yaml(path)
