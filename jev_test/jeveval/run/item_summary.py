"""무엇: 항목 요약 CLI · 입력: rules/root/tasks/splits/task · 출력: 원문 없는 JSONL · 계약 §6-2."""

import argparse
import json
from pathlib import Path

from jeveval.run.stage_inputs import BUILDERS
from jeveval.data.items.common import summarize
from jeveval.io.config import load_taskspec, read_yaml
from jeveval.io.datasets import checked_family, read_label_vocab
from jeveval.io.hashes import glob_files
from jeveval.io.sources import read_set_rows
from jeveval.io.splits import read_split_plan
from jeveval.io.tasks import read_lists
from jeveval.score.labels import rules as label_rules


def _summaries(args):
    """원본은 셋마다 한 번만 읽고 두 KoSGD 판에 같은 행을 전달한다."""
    rules = read_yaml(args.root / args.rules)
    tasks = args.root / args.tasks
    lists = read_lists(tasks / "lists")
    rules_ = label_rules(read_label_vocab(args.root / args.datasets))
    paths = [p for p in glob_files(tasks, "*.yaml") if p.stem != "b1"]
    if args.task != "all":
        paths = [p for p in paths if p.stem == Path(args.task).stem]
    if not paths:
        raise ValueError("no matching task yaml")
    cache = {}
    for path in paths:
        task = load_taskspec(path)
        if task.set not in cache:
            cache[task.set] = read_set_rows(task.set, rules["sets"][task.set], args.root)
        plan = read_split_plan(args.root / args.splits / f"{task.set}.json")
        family = checked_family(task.set, rules["sets"][task.set], args.root)
        items = BUILDERS[family].build_items(cache[task.set], plan, task, lists, rules_)
        yield dict(task=path.stem, by_stage=summarize(items))


def main(argv=None) -> int:
    """입출력을 연결하고 원문이 섞일 수 있는 예외 내용은 출력하지 않는다."""
    parser = argparse.ArgumentParser(description="Summarize evaluation items without source text")
    parser.add_argument("--rules", type=Path, default=Path("configs/splits/rules.yaml"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--tasks", type=Path, default=Path("configs/tasks"))
    parser.add_argument("--splits", type=Path, default=Path("configs/splits"))
    parser.add_argument("--datasets", type=Path, default=Path("configs/datasets.yaml"))
    parser.add_argument("--task", required=True)
    args = parser.parse_args(argv)
    try:
        for summary in _summaries(args):
            print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    except (ValueError, KeyError, TypeError, OSError, AttributeError, IndexError) as exc:
        parser.exit(1, f"item_summary: invalid input ({type(exc).__name__})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
