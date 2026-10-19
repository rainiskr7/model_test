"""무엇: 보고 부가 입력 읽기 · 입력: 명시 compare ID/셋/판 · 출력: 파일 schema · 계약 §7-6."""

from pathlib import Path

from jeveval.io import run_files
from jeveval.io.set_config import entry
from jeveval.io.set_tasks import primary_variant
from jeveval.io.paths import identifier, inside


def compare(root, results, compare_id, set_name, variant):
    parts = [identifier(v) for v in (compare_id, set_name, variant)]
    path = inside(root, Path(results) / "_compare" / parts[0] / "A" / parts[1] / parts[2] / "compare.json")
    return run_files.read_json(path) if path.exists() else None


def metadata(root, set_name, variant):
    selected = entry(root, set_name)
    return selected.family, primary_variant(root, selected) == variant


def output(root, path):
    """기존 원기록/설정을 덮어쓰지 않도록 Markdown 출력만 허용한다."""
    target = inside(root, path)
    if target.suffix != ".md" or target.name in ("P1_CONTRACT.md", "JEV_TEST_PLAN.md", "README.md", "NOTES.md"):
        raise ValueError("report output must be a dedicated Markdown file")
    return target
