"""무엇: nodeid/skip 보존 검사 · 입력: 수집 manifest · 출력: 회귀 검출 · 계약 §9 C1."""

from audits.stage2_20261021.shape_check import nodeids


def test_nodeid_deletion_and_new_skips_are_not_hidden():
    assert not nodeids({'old': []}, {'old': [], 'new': []})
    assert nodeids({'old': []}, {'new': []})
    assert nodeids({'old': []}, {'old': ['skip']})
    assert nodeids({}, {'new': ['xfail']})
    assert not nodeids({'old': ['skipif']}, {'old': ['skipif']})
