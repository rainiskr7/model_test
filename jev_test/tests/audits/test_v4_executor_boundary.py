"""무엇: 감사 공개 실행기 경계 · 입력: 감사 AST · 출력: private/전역 기록 patch 부재 · 계약 §2-2."""

import ast
from pathlib import Path


def test_audit_uses_public_executor_and_no_record_patch():
    root = Path(__file__).resolve().parents[2] / "audits/audit_v4"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            assert not isinstance(node, ast.Name) or node.id != "_execute_call"
            assert not isinstance(node, ast.Attribute) or node.attr not in ("_execute_call", "append_record")
            assert not isinstance(node, ast.alias) or node.name not in ("_execute_call", "append_record")
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "_execute_call" not in node.value and "append_record" not in node.value
