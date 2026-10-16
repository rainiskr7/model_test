"""무엇: 저장소 안 경로 제한·결과 식별자·파일 stat · 입력: root·상대 경로·문자열 · 출력: 검증된 Path/str/(크기, mtime) · 계약 §5-1·§8-1."""

from pathlib import Path
import re


def identifier(value) -> str:
    """결과 경로 조각으로 쓸 수 있는 식별자만 통과시킨다."""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ValueError("invalid result identifier")
    return value


def inside(root, path) -> Path:
    """root 를 벗어나는(.. 또는 symlink) 경로를 거부하고 절대 경로를 돌려준다."""
    root = Path(root).resolve()
    result = (root / path).resolve()
    if not result.is_relative_to(root):
        raise ValueError("path outside repository")
    return result


def file_info(path) -> tuple[int, float]:
    """파일 크기와 mtime 만 읽는다. 내용은 열지 않는다."""
    stat = Path(path).stat()
    return stat.st_size, stat.st_mtime
