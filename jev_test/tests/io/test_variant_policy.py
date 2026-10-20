"""무엇: 닫힌 변형 정책 · 입력: manifest/종류 혼동 · 출력: 해시/거부 · 계약 §7-4d."""

from pathlib import Path
import pytest
from jeveval.io import variant_policy, analysis
from tests.run.file_support import put_yaml


def test_exact_policy_and_wrong_kind(tmp_path):
    root = Path(__file__).resolve().parents[2]
    value, digest = variant_policy.policy(root)
    assert len(digest) == 64 and value['candidates'][0] == 'min'
    with pytest.raises(ValueError): analysis.load_policy(root, 'question_risk', variant_policy.MANIFEST)
    with pytest.raises(ValueError): analysis.load_policy(root, 'score_variants', analysis.MANIFEST)
    value['apply'] = 'linear'
    put_yaml(tmp_path / variant_policy.MANIFEST, value)
    with pytest.raises(ValueError): variant_policy.policy(tmp_path)


def test_broken_policy_is_a_safe_value_error(tmp_path):
    path = tmp_path / variant_policy.MANIFEST
    path.parent.mkdir(parents=True)
    path.write_text('schema: [')
    with pytest.raises(ValueError, match='invalid variant policy YAML'):
        variant_policy.policy(tmp_path)
