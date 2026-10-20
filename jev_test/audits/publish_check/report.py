"""무엇: 검사 증거 조립·저장. 입력: 집계·지정 외부 경로. 출력: 원문 없는 JSON·도구 해시."""

from hashlib import sha256
import json
from pathlib import Path


def tool_sha():
    digest = sha256()
    directory = Path(__file__).parent
    for path in sorted(directory.glob("*.py")):
        digest.update(path.name.encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def output_path(repo, out):
    repo, out = Path(repo).resolve(), Path(out).resolve()
    if out.is_relative_to(repo) or out.exists():
        raise ValueError("new output outside repository required")
    if not out.parent.is_dir():
        raise ValueError("output parent missing")
    return out


def write(path, value):
    # Exclusive creation also rejects a destination created after preflight.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=True, sort_keys=True, indent=1)
        stream.write("\n")
