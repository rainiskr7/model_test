"""무엇: 외부 코드·패키지 지문 · 입력: jev_test 루트 · 출력: 해시/버전 · 계약 §8-7 T-j."""

from importlib.metadata import version
from pathlib import Path, PurePosixPath
import platform

from jeveval.io.hashes import sha256_file

EXTERNAL_FILES = ("reranker_test/evalcommon/schema.py",)
PACKAGES = {"numpy": "numpy", "scipy": "scipy", "zstandard": "zstandard", "pyyaml": "PyYAML"}


def external_path(root, name):
    """model_test 내부의 명시적 외부 코드만 허용하며 symlink 탈출도 거부한다."""
    relative = PurePosixPath(name)
    if (not name or relative.is_absolute() or ".." in relative.parts or relative.as_posix() != name
            or "\\" in name or "\x00" in name or name not in EXTERNAL_FILES):
        raise ValueError("invalid external source path")
    parent = Path(root).resolve().parent
    path = (parent / name).resolve()
    if not path.is_relative_to(parent) or not path.is_file():
        raise ValueError("external source missing or outside repository")
    return path


def external_hashes(root):
    return {name: sha256_file(external_path(root, name)) for name in EXTERNAL_FILES}


def versions():
    """설치된 배포 메타데이터를 읽는다. 필수 패키지 누락은 숨기지 않는다."""
    return dict(python=platform.python_version(), **{key: version(name) for key, name in PACKAGES.items()})
