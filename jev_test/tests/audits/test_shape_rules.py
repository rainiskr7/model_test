"""무엇: AST 경계 공격 · 입력: 합성 Python · 출력: 길이/의존/효과 거부 · 계약 §9 C1."""

from audits.stage2_20261021.shape_rules import violations

DOC = '"""무엇: 합성 · 입력: 없음 · 출력: 없음 · 계약 §9."""\n'


def test_dependency_effect_and_literal_conditions():
    for code in ('from jeveval.contract import stages\n', 'from ..io import run_files\n',
                 'def f():\n    return open("a")\n', 'if name == "kosgd":\n    pass\n',
                 'def f():\n    return metric_spec("x")\n'):
        assert violations('jeveval/score/example.py', DOC + code)
    assert not violations('jeveval/score/example.py', DOC + 'from jeveval.types import Item\n')


def test_docstring_and_line_limits():
    assert violations('test.py', 'x=1\n')
    assert violations('test.py', DOC + '\n'*201)
    assert violations('test.py', DOC + 'def f():\n' + '    pass\n'*51)
