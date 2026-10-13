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


def glob_files(directory, pattern) -> list[Path]:
    """패턴에 맞는 파일 경로를 정렬하여 반환한다. 내용은 읽지 않는다."""
    return sorted(p for p in Path(directory).glob(pattern) if p.is_file())


def code_sha256(root) -> str:
    """root 상대 POSIX 경로·NUL·내용을 경로순으로 이어 Python 소스를 해시한다."""
    root = Path(root)
    digest = hashlib.sha256()
    for path in glob_files(root / "jeveval", "**/*.py"):
        if "__pycache__" in path.relative_to(root / "jeveval").parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def tokenizer_sha256(directory, expected) -> dict[str, str]:
    """명시된 토크나이저 파일을 재해시하고 누락·탈출·불일치를 거부한다."""
    if not isinstance(expected, dict) or not expected:
        raise ValueError("incomplete tokenizer hashes")
    directory = Path(directory).resolve()
    actual = {}
    for name, digest in sorted(expected.items()):
        path = (directory / name).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            raise ValueError("tokenizer file missing or outside directory")
        actual[name] = sha256_file(path)
        if actual[name] != digest:
            raise ValueError("tokenizer hash mismatch")
    return actual
