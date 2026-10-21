"""무엇: AST 본문 정규화 시험 · 입력: 이름/동작 차이 · 출력: 동일/상이 해시 · 계약 §9."""

from audits.serverless_20261021.function_shapes import functions


def test_arguments_locals_and_docstrings_are_normalized():
    a = 'def f(value):\n "one"\n x = value + 1\n y = x * 2\n return y\n'
    b = 'def g(other):\n "two"\n first = other + 1\n second = first * 2\n return second\n'
    assert functions(a)[0]['digest'] == functions(b)[0]['digest']
    assert functions(a)[0]['digest'] != functions(b.replace('* 2', '* 3'))[0]['digest']
    assert functions('def f(x):\n return x\n') == []


def test_globals_and_attributes_are_not_normalized():
    source = 'def f(x):\n a = SERVICE.read(x)\n b = a.ok\n return b\n'
    assert functions(source)[0]['digest'] != functions(source.replace('SERVICE', 'OTHER'))[0]['digest']
    assert functions(source)[0]['digest'] != functions(source.replace('.ok', '.bad'))[0]['digest']


def test_method_qualified_names_and_lines_are_reported():
    rows = functions('class C:\n def f(self, x):\n  y=x\n  z=y\n  return z\n')
    assert rows[0]['name'] == 'C.f' and rows[0]['line'] == 2


def test_nested_scope_import_alias_and_comprehension_bindings():
    source = ('def f(value):\n import math as maths\n def inner(item):\n  return maths.sqrt(item) + value\n'
              ' result = [inner(element) for element in value]\n return result\n')
    renamed = source.replace('value', 'items').replace('maths', 'numbers').replace('inner', 'nested').replace('item)', 'entry)').replace('sqrt(item)', 'sqrt(entry)').replace('element', 'part').replace('result', 'answer')
    # 이름만 달라져도 닫힌 함수/수집식의 바인딩 범위는 같다.
    assert functions(source)[0]['digest'] == functions(renamed)[0]['digest']
    foreign = 'def f(values):\n data = [x for x in values]\n size = len(data)\n return x + size\n'
    assert functions(foreign)[0]['digest'] != functions(foreign.replace('return x', 'return y'))[0]['digest']
