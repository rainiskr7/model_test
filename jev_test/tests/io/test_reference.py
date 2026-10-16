"""무엇: 로컬 소스 로딩·가벼운 import · 입력: 합성 모듈 · 출력: 캐시 없는 모듈 · 계약 §8-6 H·I."""

from pathlib import Path
import os
import subprocess
import sys

import pytest

from jeveval.io import reference
from jeveval.io.reference import source_module


def test_offline_environment_sets_and_preserves_both_flags(monkeypatch):
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        monkeypatch.setenv(key, "0")
    reference.offline_environment()
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    reference.offline_environment()
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


def test_local_checkpoint_uses_offline_environment(tmp_path, monkeypatch):
    calls, original = [], reference.offline_environment
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        monkeypatch.setenv(key, "0")

    def offline():
        calls.append("offline")
        original()

    monkeypatch.setattr(reference, "offline_environment", offline)
    assert reference.local_checkpoint(tmp_path) == tmp_path.resolve()
    assert calls == ["offline"]


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


@pytest.fixture
def package(tmp_path, monkeypatch):
    name = "_jev_test_reference"
    monkeypatch.setattr(sys, "path", list(sys.path))
    for key in (name, name + ".model", name + ".types"):
        monkeypatch.setitem(sys.modules, key, sys.modules.get(key))
        monkeypatch.delitem(sys.modules, key)
    folder = tmp_path / name
    folder.mkdir()
    (folder / "__init__.py").write_text("")
    (folder / "types.py").write_text("VALUE = 42\n")
    (folder / "model.py").write_text("from .types import VALUE\n")
    return tmp_path, name + ".model"


def test_package_module_loads_relative_import_and_reuses_same_location(package):
    root, name = package
    module = reference.package_module(root, name)
    assert module.VALUE == 42
    assert Path(module.__file__).resolve().is_relative_to(root)
    assert reference.package_module(root, name) is module
    assert sys.path.count(str(root)) == 1


def test_package_module_requires_source_directory(tmp_path):
    before = list(sys.path)
    with pytest.raises(ValueError, match="^reference source directory required$"):
        reference.package_module(tmp_path / "missing", "not_imported.model")
    assert sys.path == before


@pytest.mark.parametrize("loaded", ["module", "package"])
@pytest.mark.parametrize("has_file", [True, False])
def test_package_module_prechecks_location_before_import(package, monkeypatch, loaded, has_file):
    import importlib
    from types import ModuleType
    root, name = package
    key = name if loaded == "module" else name.split(".")[0]
    other = ModuleType(key)
    if has_file:
        other.__file__ = str(root.parent / "elsewhere/model.py")
    monkeypatch.setitem(sys.modules, key, other)
    def forbidden(*args, **kwargs):
        pytest.fail("foreign cached module reached import")
    monkeypatch.setattr(importlib, "import_module", forbidden)
    before, bytecode = list(sys.path), sys.dont_write_bytecode
    with pytest.raises(ValueError) as error:
        reference.package_module(root, name)
    assert str(error.value) == f"{key} is already imported from a different location"
    assert sys.modules[key] is other
    assert sys.path == before and sys.dont_write_bytecode is bytecode


@pytest.mark.parametrize("previous", [False, True])
@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("already_on_path", [False, True])
def test_package_module_restores_bytecode_and_failed_import_path(
        package, monkeypatch, previous, fail, already_on_path):
    root, name = package
    module_path = root / name.replace(".", "/")
    module_path.with_suffix(".py").write_text(
        "import sys\nDISABLED = sys.dont_write_bytecode\nassert DISABLED\n" +
        ("raise RuntimeError('synthetic import failure')\n" if fail else "from .types import VALUE\n"))
    monkeypatch.setattr(sys, "dont_write_bytecode", previous)
    if already_on_path:
        sys.path.append(str(root))
    before = list(sys.path)
    if fail:
        with pytest.raises(RuntimeError, match="^synthetic import failure$"):
            reference.package_module(root, name)
        assert sys.path == before
    else:
        module = reference.package_module(root, name)
        assert module.DISABLED is True and module.VALUE == 42
        assert sys.path == (before if already_on_path else [str(root), *before])
    assert sys.dont_write_bytecode is previous
    assert list(root.rglob("*.pyc")) == [] and list(root.rglob("__pycache__")) == []


def test_package_module_post_import_rejection_restores_path(package):
    """미캐시 패키지를 다른 검색 경로에서 찾은 경우도 실패한 로딩이다."""
    root, name = package
    requested = root / "empty_source"
    requested.mkdir()
    sys.path.insert(0, str(root))
    before, bytecode = list(sys.path), sys.dont_write_bytecode
    with pytest.raises(ValueError) as error:
        reference.package_module(requested, name)
    assert str(error.value) == f"{name} is already imported from a different location"
    assert sys.dont_write_bytecode is bytecode
    assert sys.path == before
