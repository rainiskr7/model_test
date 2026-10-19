"""무엇: 단계 소유 단일화 · 입력: 원 셋/별칭 · 출력: 기존 단계와 AST 경계 · 계약 §6-1."""

import ast
from pathlib import Path

import pytest

from jeveval.contract.stages import stage_names, supports_extra


@pytest.mark.parametrize("name,expected", [
    ("fc_call_decision", ("dev", "test", "extra")),
    ("kosgd", ("dev", "test")), ("kosgd2", ("dev", "test")),
    ("fc_alias", ("dev", "test")), ("unknown", ("dev", "test")),
    (None, ("dev", "test")),
])
def test_stage_names_keep_legacy_set_identity(name, expected):
    assert stage_names(name) == expected
    assert supports_extra(name) == ("extra" in expected)


def test_stage_literal_only_in_owner_or_explicit_semantic_registry_sites():
    """파일 단위 예외로 새 분기를 숨기지 않고 함수별 문자열 사용 횟수까지 고정한다."""
    root = Path(__file__).resolve().parents[2]
    allowed = {
        ("contract/stages.py", "stage_names"): 1,
        ("io/set_tasks.py", "<module>"): 1,
        ("io/sources/__init__.py", "<module>"): 1,
        ("io/sources/functionchat.py", "read_rows"): 1,
        ("run/stage_inputs.py", "<module>"): 1,
        ("score/population.py", "_specific"): 1,
        ("score/population.py", "_set_rows"): 1,
        ("score/population.py", "population"): 1,
        ("score/observations.py", "observations"): 1,
        ("score/observations.py", "question_ids"): 1,
        ("score/bootstrap.py", "f1_diff"): 1,
    }
    found = {}
    for path in (root / "jeveval").rglob("*.py"):
        tree = ast.parse(path.read_text())
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or node.value != "fc_call_decision":
                continue
            owner = node
            while owner in parents and not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                owner = parents[owner]
            key = path.relative_to(root / "jeveval").as_posix(), getattr(owner, "name", "<module>")
            found[key] = found.get(key, 0) + 1
    assert found == allowed
    tree = ast.parse((root / "audits/replay_20261019/c3_compare_runs.py").read_text())
    assert not any(isinstance(n, ast.Constant) and n.value == "fc_call_decision" for n in ast.walk(tree))
