"""Archive code and copy input data once, keeping their roots separate."""

import hashlib
import shutil
import subprocess
import tarfile
from pathlib import Path

from tools.output_baseline.inputs import copy_roots, file_manifest, sha256


def git(base, *args):
    return subprocess.check_output(["git", "-C", str(base), *args])


def archive_code(base, destination, evidence):
    # Archive every tracked top-level code/document path, excluding live datasets.
    names = git(base, "ls-tree", "--name-only", "HEAD", "./").decode().splitlines()
    names = [name for name in names if name not in {"results", "data"}]
    archive = evidence / "head.tar"
    with archive.open("wb") as stream:
        subprocess.run(["git", "-C", str(base), "archive", "HEAD", "--", *names],
                       stdout=stream, check=True)
    destination.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination, filter="data")
    return {"head": git(base, "rev-parse", "HEAD").decode().strip(),
            "archive_sha256": sha256(archive), "archive_paths": names}


def dirty_state(base, evidence):
    diff = git(base, "diff", "HEAD", "--binary", "--", ".")
    (evidence / "working.diff").write_bytes(diff)
    paths = git(base, "ls-files", "--others", "--exclude-standard", "-z", "--", ".")
    # Results are live report inputs, never part of the code dirty fingerprint.
    untracked = {name: sha256(base / name) for name in paths.decode().split("\0")
                 if name and Path(name).parts[0] not in {"results", "data"}
                 and (base / name).is_file()}
    return {"tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
            "untracked_code_sha256": untracked}


def copy_inputs(base, destination, entries):
    destination.mkdir()
    roots = copy_roots(entries)
    required = sorted(set(roots) | {item["path"] for item in entries})
    for relative in required:
        if not (base / relative).exists():
            raise FileNotFoundError(f"missing input: {relative}")
    for relative in roots:
        source, target = base / relative, destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    return {"root": str(destination), "required": required,
            "files": file_manifest(destination)}
