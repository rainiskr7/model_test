"""무엇: run_id 단위 보존 조립 · 입력: 완료 run 전체 · 출력: archive.json · 계약 §8-6 F·⑥b-2 R4."""

from pathlib import Path

from jeveval.io import archive, run_files
from jeveval.io.paths import identifier, inside
from jeveval.run import context
from jeveval.run.layout import run_dir


def run(*, root, run_id, results="results", archive_root="archive"):
    path = inside(root, Path(archive_root) / f"{identifier(run_id)}.tar.zst")
    directories = archive.run_directories(root, results, run_id)
    if not directories or run_files.exists(path) or any(
            run_files.exists(d / "archive.json") for d in directories):
        raise ValueError("missing runs or already archived")
    contexts, warnings = [], []
    for directory in directories:
        ctx, stages, threshold = context.completed(root, directory)
        expected = run_dir(inside(root, results), ctx.cfg.id, run_id, ctx.task.set, ctx.task.variant)
        if ctx.fingerprint["run_id"] != run_id or directory != expected:
            raise ValueError("archive run identity differs")
        for name in ("scores.json", "risk.json"):
            context.check_identity(ctx, run_files.read_json(directory / name))
        contexts.append(ctx)
        warnings.extend(w for data in stages.values() for w in data.warnings)
    entries = archive.entries_for(root, contexts)
    run_files.make_directory(path.parent)
    metadata = archive.build_archive(entries, path)
    metadata["archive"] = path.relative_to(Path(root).resolve()).as_posix()
    for ctx in contexts:
        run_files.write_json(ctx.directory / "archive.json", metadata)
    return dict(ok=True, warnings=warnings)
