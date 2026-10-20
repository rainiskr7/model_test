"""Writable smoke state is always outside the code and linked input trees."""
import os
from pathlib import Path
import shutil
import tempfile

REVISION = "62128c281b7fcbd5af77593a6b65aa385554cb71"


class Unavailable(Exception):
    """A prerequisite is unavailable; this is not a serving verdict."""


def outside(path, root):
    path = Path(path).resolve()
    if path.is_relative_to(root.resolve()):
        raise ValueError("smoke output/temp directory must be outside the code root")
    return path


def assemble(root):
    # Do not trust a caller's TMPDIR (it could point into N/data).
    base = Path(tempfile.mkdtemp(prefix="serving-smoke-", dir="/tmp")).resolve()
    try:
        outside(base, root)
        for name in ("data", "configs", "shared"):
            (base / name).symlink_to(root / name, target_is_directory=True)
        for source in root.glob(".venv*"):
            (base / source.name).symlink_to(source, target_is_directory=True)
        for name in ("results", "logs", "cache", "tmp", "kreta_output"):
            (base / name).mkdir()
    except (Exception, KeyboardInterrupt):
        # Ownership is local even when construction never returns a BASE to main.
        shutil.rmtree(base)
        raise
    return base


def environment(root, base, stamp):
    # No inherited provider credentials, proxy, telemetry or stale serving knobs.
    env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL") if k in os.environ}
    env.update(MODEL_TEST_BASE=str(base), PYTHONPATH=str(root),
               PYTHONDONTWRITEBYTECODE="1", EVAL_TIMESTAMP=stamp,
               TMPDIR=str(base / "tmp"), XDG_CACHE_HOME=str(base / "cache"),
               KRETA_OUTPUT_ROOT=str(base / "kreta_output"),
               HF_HOME=str(base / "cache/hf"), HF_HUB_OFFLINE="1",
               HF_DATASETS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
               HF_DATASETS_CACHE=str(base / "cache/hf/datasets"),
               HF_HUB_CACHE=str(base / "cache/hf/hub"),
               HF_MODULES_CACHE=str(base / "cache/hf/modules"),
               HF_ASSETS_CACHE=str(base / "cache/hf/assets"),
               TOKENIZERS_PARALLELISM="false", DO_NOT_TRACK="1")
    return env


def copy_cache(base, source=None):
    source = source or Path.home() / ".cache/huggingface"
    names = ("datasets/NCSOFT___k-dtc_bench", "hub/datasets--NCSOFT--K-DTCBench")
    for name in names:
        if not (source / name).is_dir():
            raise Unavailable(f"offline K-DTCBench cache missing: {source / name}")
    for name in names:
        target = base / "cache/hf" / name
        # symlinks=False dereferences snapshot links; never hard-link cache files.
        shutil.copytree(source / name, target, symlinks=False,
                        ignore=shutil.ignore_patterns("*.lock"))
    arrows = base / "cache/hf/datasets/NCSOFT___k-dtc_bench"
    if not list(arrows.glob(f"**/{REVISION}/*.arrow")):
        raise Unavailable(f"offline dataset revision {REVISION} unavailable")
    return REVISION
