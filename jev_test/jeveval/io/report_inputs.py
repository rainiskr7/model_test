"""무엇: 보고 부가 입력 읽기 · 입력: 명시 compare ID/셋/판 · 출력: 파일 schema · 계약 §7-6."""

from pathlib import Path

from jeveval.io import run_files
from jeveval.io.config import load_taskspec, read_yaml
from jeveval.io.datasets import dataset_entry, family
from jeveval.io.paths import identifier, inside


def compare(root, results, compare_id, set_name, variant):
    parts = [identifier(v) for v in (compare_id, set_name, variant)]
    path = inside(root, Path(results) / "_compare" / parts[0] / "A" / parts[1] / parts[2] / "compare.json")
    return run_files.read_json(path) if path.exists() else None


def metadata(root, set_name, variant):
    data = read_yaml(inside(root, "configs/datasets.yaml"))
    primary = dataset_entry(data, set_name).get("map", {}).get("primary_variant")
    if primary is None:
        tasks = inside(root, "configs/tasks")
        variants = {t.variant for p in tasks.glob("*.yaml") if p.stem != "b1"
                    for t in [load_taskspec(p)] if t.set == set_name}
        if len(variants) == 1:
            primary = variants.pop()
    return family(set_name, data), None if primary is None else primary == variant


def output(root, path):
    """기존 원기록/설정을 덮어쓰지 않도록 Markdown 출력만 허용한다."""
    target = inside(root, path)
    if target.suffix != ".md" or target.name in ("P1_CONTRACT.md", "JEV_TEST_PLAN.md", "README.md", "NOTES.md"):
        raise ValueError("report output must be a dedicated Markdown file")
    return target
