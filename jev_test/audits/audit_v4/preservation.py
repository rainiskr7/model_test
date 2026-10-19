"""실행 전후 보호 파일 집합·바이트와 새 출력 위치를 검사한다."""

import hashlib
from pathlib import Path

PROTECTED = ("audits/audit_v3", "results", "configs/t0/fixture_v1.json", "configs/tasks", "configs/datasets.yaml",
             "configs/splits", "configs/policy.yaml", "audits/kosgd2_selection/selection.json")
ALLOWED = ("audits/audit_v4/out/", "audits/kosgd2_pilot/", "results/_report/")


def snapshot(root):
    root, result = Path(root), {}
    for name in PROTECTED:
        path = root / name
        paths = [path] if path.is_file() else path.rglob("*")
        for p in paths:
            if p.is_file() and "__pycache__" not in p.parts:
                result[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def verify(before, after):
    if any(after.get(name) != digest for name, digest in before.items()):
        raise ValueError("protected input changed or removed")
    if any(not name.startswith(ALLOWED) for name in after.keys() - before.keys()):
        raise ValueError("new protected file outside allowed outputs")


def inventory(root):
    """기존 비보호 파일은 이름만 읽되 새 출력은 허용 경로 밖이면 거부할 수 있게 한다."""
    root = Path(root)
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and
            not {".git", "__pycache__", ".pytest_cache"} & set(p.relative_to(root).parts)}


def verify_outputs(before, after):
    if any(not name.startswith(ALLOWED) for name in after - before):
        raise ValueError("new output outside allowed directories")
