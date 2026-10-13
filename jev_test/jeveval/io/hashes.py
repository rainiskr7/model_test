"""무엇: 파일 해시·목록 대조 · 입력: 파일/디렉터리 · 출력: sha256/불일치 이름 · 계약 §5-6·§8-6."""

import hashlib
from pathlib import Path, PurePosixPath
import re


def sha256_file(path) -> str:
    """원문을 해석하지 않고 고정 크기 블록으로 SHA-256을 계산한다."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_sha256sums(path) -> dict[str, str]:
    """두 공백 형식의 목록을 읽고 중복·디렉터리 밖 경로를 거부한다."""
    result = {}
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-fA-F]{64})  (.+)", line)
        if not match:
            raise ValueError(f"SHA256SUMS line {number}: invalid format")
        digest, name = match.groups()
        entry = PurePosixPath(name)
        if entry.is_absolute() or ".." in entry.parts or "\\" in name or "\x00" in name:
            raise ValueError(f"SHA256SUMS line {number}: invalid name")
        if name in result:
            raise ValueError(f"SHA256SUMS line {number}: duplicate name")
        result[name] = digest.lower()
    return result


def verify_dir(directory) -> list[str]:
    """목록에 있는 파일만 해시로 대조하며 SHA256SUMS 자체는 제외한다."""
    directory = Path(directory).resolve()
    mismatches = []
    for name, expected in read_sha256sums(directory / "SHA256SUMS").items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("SHA256SUMS: file outside directory")
        if path == directory / "SHA256SUMS":
            continue
        if not path.is_file() or sha256_file(path) != expected:
            mismatches.append(name)
    return mismatches
