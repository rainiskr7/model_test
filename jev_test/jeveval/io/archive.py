"""무엇: 결정적 비공개 보존 · 입력: 이름→파일/경로 · 출력: tar.zst·검증 오류 · 계약 §5-6·⑥b-2 R4–6."""

import io
from pathlib import Path, PurePosixPath
import tarfile

from jeveval.io.hashes import sha256_file
from jeveval.io.environment import external_path
from jeveval.io.run_inputs import inside
from jeveval.run.layout import identifier


def _name(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or path.as_posix() != name or name == ".":
        raise ValueError("invalid archive member name")
    return name


def build_archive(entries, out_path):
    """이름→Path의 내용만 직렬화한다. 원본 stat 메타데이터·출력 경로는 바이트에 영향 없다."""
    import zstandard

    names = sorted(_name(name) for name in entries)
    with Path(out_path).open("xb") as output:
        with zstandard.ZstdCompressor(level=3).stream_writer(output, closefd=False) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                for name in names:
                    payload = Path(entries[name]).read_bytes()
                    info = tarfile.TarInfo(name)
                    info.size, info.mode = len(payload), 0o644
                    info.mtime = info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    archive.addfile(info, io.BytesIO(payload))
    return dict(sha256=sha256_file(out_path), nbytes=Path(out_path).stat().st_size, files=names)


def verify_archive(path, archive_json):
    """추출 없이 sha·길이·이름 목록을 확인하며 손상도 오류 목록으로 반환한다."""
    import zstandard

    errors = []
    try:
        if sha256_file(path) != archive_json["sha256"]:
            errors.append("sha256")
        if Path(path).stat().st_size != archive_json["nbytes"]:
            errors.append("nbytes")
        with Path(path).open("rb") as source, zstandard.ZstdDecompressor().stream_reader(source) as stream:
            with tarfile.open(fileobj=stream, mode="r|") as archive:
                names = [member.name for member in archive]
        if names != archive_json["files"]:
            errors.append("files")
    except (OSError, ValueError, KeyError, tarfile.TarError, zstandard.ZstdError):
        errors.append("unreadable archive")
    return errors


def run_directories(root, results, run_id):
    """fingerprint가 없는 미완료 폴더도 열거하여 전체 완료 검사에서 거부한다."""
    base = inside(root, results)
    return [inside(root, p) for p in sorted(base.glob(f"*/{identifier(run_id)}/A/*/*"))
            if p.is_dir() and p.relative_to(base).parts[0] != "_compare"]


def entries_for(root, contexts):
    entries = {}
    for ctx in contexts:
        for name, digest in ctx.fingerprint["external"].items():
            source = external_path(root, name)
            if sha256_file(source) != digest:
                raise ValueError("external source hash mismatch")
            entries["_external/" + name] = source
        paths = [inside(root, name) for name in ctx.fingerprint["files"]]
        paths.append(ctx.directory / "fingerprint.json")
        for stage in ("dev", "test", "extra"):
            folder = ctx.directory / stage
            if stage != "extra" or folder.exists() or ctx.task.set == "fc_call_decision":
                paths.extend(folder / f"{name}.jsonl" for name in ("attempts", "final"))
        for path in paths:
            path = inside(root, path)
            if not path.is_file():
                raise ValueError("archive input missing")
            entries[path.relative_to(Path(root).resolve()).as_posix()] = path
    return entries
