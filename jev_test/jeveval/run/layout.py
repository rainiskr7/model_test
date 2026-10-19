"""무엇: 결과 위치 · 입력: 루트/식별자 · 출력: 제한된 경로 · 계약 §5-1·⑥b R5."""

from pathlib import Path

from jeveval.io.paths import identifier


def _path(root, *parts):
    root = Path(root).resolve()
    path = root.joinpath(*parts).resolve()
    if not path.is_relative_to(root):
        raise ValueError("result path outside root")
    return path


def run_dir(results_root, model_id, run_id, set, variant):
    return _path(results_root, identifier(model_id), identifier(run_id), "A",
                 identifier(set), identifier(variant))


def compare_dir(results_root, compare_id, set, variant):
    return _path(results_root, "_compare", identifier(compare_id), "A",
                 identifier(set), identifier(variant))


def report_path(results_root, run_id):
    return _path(results_root, "_report", identifier(run_id) + ".md")
