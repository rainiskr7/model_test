"""무엇: 단계 입력 복원 · 입력: 동결 설정/실행 경로·단계 · 출력: Item/기록·경고 · 계약 §8-6 E."""

from pathlib import Path

from jeveval.data.items import functionchat, klue_mrc, kmhas, korfin, kosgd, kote
from jeveval.io.config import load_taskspec
from jeveval.io.datasets import read_label_vocab
from jeveval.io.hashes import verify_dir
from jeveval.io.set_config import entry
from jeveval.io.set_tasks import require_task
from jeveval.io.records import read_finals
from jeveval.io.sources import read_set_rows
from jeveval.io.splits import read_split_plan
from jeveval.io.tasks import read_lists
from jeveval.score.labels import rules as label_rules
from jeveval.types import FinalRecord, Item


BUILDERS = {"kosgd": kosgd, "fc_call_decision": functionchat, "kmhas": kmhas,
            "kote_escalation": kote, "korfin_asc": korfin, "klue_mrc_answerable": klue_mrc}


def _stage(stage):
    """단계 이름을 제한해 실행 폴더 밖 경로를 만들지 않는다."""
    if stage not in ("dev", "test", "extra"):
        raise ValueError("invalid stage")
    return stage


def load_items(*, root, task_path, stage) -> list[Item]:
    """공유 원본·설정을 읽고 기존 builder 결과 중 요청한 단계만 반환한다."""
    _stage(stage)
    root = Path(root)
    task = load_taskspec(root / task_path)
    if verify_dir(root / "dataset" / task.set):
        raise ValueError("dataset hash mismatch")
    selected = entry(root, task.set)
    require_task(root, selected, task_path)
    rows = read_set_rows(task.set, selected.split_rules, root, selected=selected)
    plan = read_split_plan(root / "configs/splits" / f"{task.set}.json")
    lists = read_lists(root / "configs/tasks/lists")
    rules_ = label_rules(read_label_vocab(root / "configs/datasets.yaml"))
    return BUILDERS[selected.family].build_items(rows, plan, task, lists, rules_)[stage]


def final_path(run_dir, stage):
    """그 단계 final 경로만 계산하며 파일 시스템을 조회하지 않는다."""
    return Path(run_dir) / _stage(stage) / "final.jsonl"


def attempts_path(run_dir, stage):
    """그 단계 attempts 경로만 계산한다."""
    return Path(run_dir) / _stage(stage) / "attempts.jsonl"


def read_stage_finals(run_dir, stage) -> tuple[list[FinalRecord], list[str]]:
    """다른 단계 경로를 열지 않고 기록과 끝 줄 경고를 함께 반환한다."""
    return read_finals(final_path(run_dir, stage))
