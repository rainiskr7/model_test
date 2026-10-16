"""무엇: 참조 구현 로컬 로딩 경계 · 입력: 체크포인트/소스 · 출력: 경로/모듈 · 계약 §8-6 H·I."""

import os
from pathlib import Path


def offline_environment() -> None:
    """모델/토크나이저 import 전에 다운로드 경로를 끈다. 설정은 뒤의 로딩에도 유지된다."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"


def local_checkpoint(path):
    """Hub 식별자를 로컬 폴더로 대체하지 않으며 다운로드를 허용하지 않는다."""
    checkpoint = Path(path).resolve()
    if not checkpoint.is_dir():
        raise ValueError("local checkpoint directory required")
    offline_environment()
    return checkpoint


def source_module(path, name):
    """받아 둔 참조 소스를 수정/복사하거나 bytecode를 쓰지 않고 import한다."""
    from importlib.machinery import SourceFileLoader
    from importlib.util import module_from_spec, spec_from_file_location
    import sys

    class ReadOnlyLoader(SourceFileLoader):
        def set_data(self, path, data, **kwargs):
            pass

    spec = spec_from_file_location(name, path, loader=ReadOnlyLoader(name, str(path)))
    module = module_from_spec(spec)
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    return module


def package_module(source_root, name):
    """체크포인트 사본의 source 폴더를 sys.path 앞에 두고 패키지 모듈을 import 한다 (예: autojev.model).

    같은 이름(또는 그 최상위 패키지)이 다른 위치에서 이미 import 돼 있으면 **import 전에** 거부한다 — 한 프로세스는 한 사본의 코드만 쓴다.
    실패하면 sys.path 를 되돌리고, 사본 폴더에 bytecode 를 쓰지 않는다.
    """
    import importlib
    import sys

    root = Path(source_root).resolve()
    if not root.is_dir():
        raise ValueError("reference source directory required")
    for loaded in (name, name.split(".")[0]):
        file = getattr(sys.modules.get(loaded), "__file__", None)
        if sys.modules.get(loaded) is not None and (file is None or not Path(file).resolve().is_relative_to(root)):
            raise ValueError(f"{loaded} is already imported from a different location")
    inserted = str(root) not in sys.path
    if inserted:
        sys.path.insert(0, str(root))
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        module = importlib.import_module(name)
    except Exception:
        if inserted:
            sys.path.remove(str(root))
        raise
    finally:
        sys.dont_write_bytecode = previous
    file = getattr(module, "__file__", None)
    if file is None or not Path(file).resolve().is_relative_to(root):
        if inserted:
            sys.path.remove(str(root))
        raise ValueError(f"{name} is already imported from a different location")
    return module
