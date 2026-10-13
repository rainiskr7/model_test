"""무엇: 로컬 소스 로딩·가벼운 import · 입력: 합성 모듈 · 출력: 캐시 없는 모듈 · 계약 §8-6 H·I."""

from pathlib import Path
import subprocess
import sys

import pytest

from jeveval.io.reference import source_module


def test_readonly_source_import_supports_dataclasses(tmp_path):
    path = tmp_path / "reference.py"
    path.write_text("from dataclasses import dataclass\n@dataclass\nclass Result:\n    value: int\n")
    module = source_module(path, "_test_local_reference")
    assert module.Result(2).value == 2
    assert list(tmp_path.iterdir()) == [path]
    path.write_text("raise ValueError('bad source')\n")
    with pytest.raises(ValueError):
        source_module(path, "_test_local_reference")
    assert sys.modules["_test_local_reference"] is module
    sys.modules.pop("_test_local_reference")


def test_reference_import_does_not_import_heavy_modules():
    root = Path(__file__).parents[2]
    script = ("import sys; sys.path.insert(0, sys.argv[1]); "
              "import jeveval.reference.clef_runner, jeveval.reference.pplx_runner; "
              "assert not {'torch', 'transformers', 'autojev'} & sys.modules.keys()")
    result = subprocess.run([sys.executable, "-B", "-I", "-c", script, str(root)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
