"""Resolve existing result model directory spelling."""

from pathlib import Path


def safe_model_name(model: str) -> str:
    """Normalize model name for filesystem path.

    Examples:
        Qwen/Qwen3.5-35B-A3B → Qwen_Qwen3.5_35B_A3B
        google/gemma-4-26B-A4B → google_gemma_4_26B_A4B
    """
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


def results_model_dir_name(base_dir: Path, model: str) -> str:
    """Reuse the sole case-fold-equivalent model directory spelling.

    macOS commonly hides casing drift that breaks a Linux clone.  If exactly
    one existing directory matches, its on-disk spelling is authoritative.
    Multiple case-fold matches are unsafe and are rejected.
    """

    requested = safe_model_name(model)
    results_root = Path(base_dir) / "results"
    if not results_root.is_dir():
        return requested
    matches = sorted(
        entry.name for entry in results_root.iterdir()
        if entry.is_dir() and entry.name.casefold() == requested.casefold()
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"case-fold ambiguous results model directory for {requested!r}: {matches}"
        )
    return requested
