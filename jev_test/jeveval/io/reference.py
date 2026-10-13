"""무엇: 참조 구현 로컬 로딩 경계 · 입력: 체크포인트/소스 · 출력: 경로/모듈 · 계약 §8-6 H·I."""

import os
from pathlib import Path


def local_checkpoint(path):
    """Hub 식별자를 로컬 폴더로 대체하지 않으며 다운로드를 허용하지 않는다."""
    checkpoint = Path(path).resolve()
    if not checkpoint.is_dir():
        raise ValueError("local checkpoint directory required")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
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
