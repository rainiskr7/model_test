"""무엇: 순수 시험의 Arrow 격리 · 입력: 고정 6파일 · 출력: 차단 하위 pytest 성공 · 계약 §9."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap


FILES = tuple(f"tests/run/test_{name}.py" for name in
              ("policy", "outcome", "plan_calls", "length", "derive", "layout"))


def test_six_files_run_without_pyarrow(tmp_path):
    """pytest를 import하기 전 차단하며 자식에서 자기 자신을 수집하지 않는다."""
    root = Path(__file__).resolve().parents[2]
    assert Path(__file__).relative_to(root).as_posix() not in FILES
    script = textwrap.dedent('''
        import importlib.abc
        import sys

        class BlockArrow(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "pyarrow" or fullname.startswith("pyarrow."):
                    raise ImportError("pyarrow forbidden by unit isolation")

        assert not any(n == "pyarrow" or n.startswith("pyarrow.") for n in sys.modules)
        sys.meta_path.insert(0, BlockArrow())
        import pytest

        class Collected:
            count = 0
            def pytest_collection_finish(self, session):
                self.count = len(session.items)

        collected = Collected()
        result = pytest.main(["-q", "-p", "no:cacheprovider", *sys.argv[1:]], plugins=[collected])
        assert collected.count > 0, "empty isolated suite"
        assert result == 0, "isolated pytest failed"
        assert not any(n == "pyarrow" or n.startswith("pyarrow.") for n in sys.modules)
        print("UNIT_ISOLATION_COLLECTED=" + str(collected.count))
    ''')
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-B", "-c", script,
                             "--confcutdir", str(root), "--basetemp", str(tmp_path / "child"), *FILES],
                            cwd=root, env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "UNIT_ISOLATION_COLLECTED=" in result.stdout
