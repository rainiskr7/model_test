"""무엇: 보호 시험 실행기 계약 · 입력: runner AST · 출력: 보호 경로 고정 · 계약 §9 C1."""

import ast
from pathlib import Path


def test_runner_protects_all_three_production_roots():
    path = Path(__file__).resolve().parents[2] / 'audits/stage2_20261021/test_runner.py'
    tree = ast.parse(path.read_text())
    constants = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert {'dataset', '.work', 'results', 'open', 'os.listdir', 'os.scandir'} <= constants
