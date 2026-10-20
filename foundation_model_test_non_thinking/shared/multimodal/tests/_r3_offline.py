"""Opt-in R3 pytest guard: synthetic fixtures only, with sockets blocked."""

import inspect
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
EXCLUDED = {
    "test_sidecar_artifact_paths_match_git_index_casing",
    "test_kreta_patch_applies_to_pinned_upstream",
    "test_upstream_evaluate_reads_only_the_given_folder",
    "test_singlecall_expansion_count_from_real_data",
    "test_stale_and_damaged_native_are_not_the_same_condition",
}
EXCLUDED_FILES = {"test_publish_dataset_identity.py", "test_publish_contamination.py"}


@pytest.fixture(autouse=True)
def synthetic_legacy_nlu_key(request, monkeypatch):
    """Keep legacy manifest tests independent of the repository dotenv file."""
    if request.node.path.name == "test_nlu_runner.py" and request.node.cls is not None:
        if request.node.cls.__name__ == "ManifestLifecycle":
            monkeypatch.setattr(request.module.runner, "load_api_key", lambda: "synthetic-key")


def pytest_collection_modifyitems(config, items):
    """Deselect existing corpus readers without modifying their test files."""
    selected, excluded = [], []
    for item in items:
        reads_corpus = (
            item.path.name in EXCLUDED_FILES or item.originalname in EXCLUDED
            or (item.path.name == "test_publish_derive.py"
                and "_copy_clean_source(" in inspect.getsource(item.obj))
        )
        (excluded if reads_corpus else selected).append(item)
    items[:] = selected
    config.hook.pytest_deselected(items=excluded)


def pytest_sessionstart(session):
    """Reject real corpus access and socket calls before collection begins."""
    protected = [str(REPO / name) for name in ("data", "results", "logs", ".env")]

    def audit(event, args):
        if event in ("socket.connect", "socket.getaddrinfo"):
            pytest.fail("R3 socket access blocked")
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            # shutil cleanup opens directory names relative to dir_fd; the
            # audit event omits that fd, so cwd would misidentify these paths.
            if args[2] & os.O_NONBLOCK:
                return
            path = os.path.abspath(os.fsdecode(args[0]))
            if any(path == prefix or path.startswith(prefix + os.sep) for prefix in protected):
                pytest.fail("R3 repository corpus access blocked: " + path)

    sys.addaudithook(audit)
