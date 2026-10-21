"""무엇: 계약 지도 검사기 시험 · 입력: 실제 문서/합성 fence·표 · 출력: 보존·누락 검출 · 계약 §9."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import pytest
from audits.serverless_20261021 import contract_map_check as check


def test_repository_map_preserves_six_blocks_and_all_tables():
    result = check.check(Path(__file__).resolve().parents[2])
    assert result['ok'], result
    assert result['rows'] == dict(issues=21, amendments=5, notes=7, preserved=6)
    assert result['blocks'] == 6


def test_fenced_headings_are_not_current_and_payload_is_exact():
    text = '## 1. current\n````markdown\n## 2. old\n```\n````\n### 1-a. detail\n'
    assert check.extract_preserved_blocks(text) == ['## 2. old\n```\n']
    assert check.index_current_sections(text) == {'1': 1, '1-a': 6}
    with pytest.raises(ValueError): check.index_current_sections('## 1. a\n## 1. b\n')
    with pytest.raises(ValueError): check.extract_preserved_blocks('````markdown\nmissing')


def test_anchor_uses_unicode_characters_and_full_preserved_excerpt():
    source = '한글' * 25 + '\n'
    digest = sha256(source[:40].encode()).hexdigest()
    assert check.verify_source_anchor(source, 1, 1, digest, [source])
    assert not check.verify_source_anchor(source, 1, 1, digest, [source[:40]])
    assert not check.verify_source_anchor(source, 1, 1, '0'*64, [source])


@pytest.mark.parametrize('kind', ['issues', 'amendments', 'notes'])
def test_missing_duplicate_rows_and_targets_fail(kind):
    root = Path(__file__).resolve().parents[2]
    rows = check.table_rows((root / 'CONTRACT_MAP.md').read_text())
    sections = {n: check.index_current_sections((root / n).read_text()) for n in check.PRESERVED}
    for attack in ('missing', 'duplicate', 'target'):
        altered = deepcopy(rows)
        if attack == 'missing': altered[kind].pop()
        elif attack == 'duplicate': altered[kind].append(altered[kind][0])
        else: altered[kind][0][4 if kind == 'issues' else 1] = '계약 §999'
        assert check.check_mapping_targets(altered, sections)
