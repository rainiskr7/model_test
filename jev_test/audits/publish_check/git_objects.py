"""무엇: 고정 커밋 전체 tree·blob 읽기. 입력: 저장소/base/head. 출력: OID별 모든 커밋·경로."""

import subprocess


def git(root, *args, input=None):
    process = subprocess.run(["git", "-C", str(root), *args], input=input, capture_output=True)
    if process.returncode:
        raise ValueError("git operation failed")
    return process.stdout


def resolve(root, revision):
    return git(root, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}").decode().strip()


def reachable_blobs(root, revision):
    objects = git(root, "rev-list", "--objects", "--no-object-names", revision)
    headers = git(root, "cat-file", "--batch-check", input=objects)
    blobs = set()
    for header in headers.decode("ascii").splitlines():
        oid, kind, _size = header.split()
        if kind == "blob":
            blobs.add(oid)
    return blobs


def inventory(root, base, head):
    base, head = resolve(root, base), resolve(root, head)
    commits = git(root, "rev-list", "--reverse", f"{base}..{head}").decode().splitlines()
    if not commits:
        raise ValueError("empty commit range")
    public_blobs = reachable_blobs(root, base)
    already_public = set()
    blobs, prohibited, unsupported = {}, [], []
    for commit in commits:
        for item in git(root, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
            if not item:
                continue
            header, path = item.split(b"\t", 1)
            mode, kind, oid = header.decode("ascii").split()
            path = path.decode("utf-8", errors="surrogateescape")
            ref = dict(commit=commit, path=path)
            if forbidden(path):
                prohibited.append(ref)
            if kind != "blob":
                unsupported.append(dict(**ref, kind=kind))
                continue
            if oid in public_blobs:
                already_public.add(oid)
                continue
            blobs.setdefault(oid, []).append(ref)
    return base, head, commits, blobs, prohibited, unsupported, len(already_public)


def forbidden(path):
    parts = path.split("/")
    if any(p in {"dataset", ".work", ".env", "archive"} for p in parts):
        return True
    if parts[-1] in {"attempts.jsonl", "final.jsonl"}:
        return True
    return any(parts[i:i + 2] == ["results", "_t0"] for i in range(len(parts) - 1)) and parts[-1] in {
        "inputs.jsonl", "reference.jsonl", "server.jsonl", "variants.jsonl"}


class CatFile:
    """batch 프로세스 하나로 읽으며 본문을 메모리에 올리기 전에 크기를 확인한다."""

    def __init__(self, root):
        self.process = subprocess.Popen(["git", "-C", str(root), "cat-file", "--batch"],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def read(self, oid, max_bytes):
        self.process.stdin.write(oid.encode("ascii") + b"\n")
        self.process.stdin.flush()
        header = self.process.stdout.readline().split()
        if len(header) != 3 or header[1] != b"blob":
            raise ValueError("blob header")
        size = int(header[2])
        # Drain oversize bodies in bounded chunks so the next batch remains aligned.
        if size > max_bytes:
            remaining = size + 1
            while remaining:
                block = self.process.stdout.read(min(remaining, 1024 * 1024))
                if not block:
                    raise ValueError("short blob")
                remaining -= len(block)
            raise ValueError("blob size limit")
        data = self.process.stdout.read(size)
        if len(data) != size or self.process.stdout.read(1) != b"\n":
            raise ValueError("short blob")
        return data

    def close(self):
        self.process.stdin.close()
        self.process.stdout.close()
        if self.process.wait(timeout=10):
            raise ValueError("cat-file failed")
