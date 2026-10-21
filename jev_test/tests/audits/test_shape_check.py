"""무엇: nodeid/skip 보존 검사 · 입력: 수집 manifest · 출력: 회귀 검출 · 계약 §9 C1."""

from audits.stage2_20261021.shape_check import nodeids


def test_nodeid_deletion_and_new_skips_are_not_hidden():
    assert not nodeids({'old': []}, {'old': [], 'new': []})
    assert nodeids({'old': []}, {'new': []})
    assert nodeids({'old': []}, {'old': ['skip']})
    assert nodeids({}, {'new': ['xfail']})
    assert not nodeids({'old': ['skipif']}, {'old': ['skipif']})


def test_new_tools_and_ops_have_explicit_shape_and_pairing_scope():
    from pathlib import Path
    import ast
    root = Path(__file__).resolve().parents[2]
    source = (root / 'audits/stage2_20261021/shape_check.py').read_text()
    constants = {n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert {'audits/serverless_20261021', 'serverless_20261021', 'ops/registration_status.py',
            'tests/ops/test_registration_status.py'} <= constants
