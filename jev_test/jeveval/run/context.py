"""무엇: 명령 입력 복원 · 입력: root/run 경로 · 출력: RunContext·StageData · 계약 §8-6 E/F/M."""

from dataclasses import replace
from pathlib import Path

from jeveval.contract.stages import stage_names
from jeveval.contract.model_config import validate_model_config
from jeveval.data.split import check_split_plan
from jeveval.io import run_files
from jeveval.io.config import load_taskspec
from jeveval.io.set_config import entry
from jeveval.io.set_tasks import primary_variant as set_primary_variant
from jeveval.io.models import load_model_config
from jeveval.io.paths import identifier, inside
from jeveval.io.policy import read_retry_policy
from jeveval.io.splits import read_split_plan
from jeveval.io.tasks import read_b1_config
from jeveval.run.fingerprint import build_fingerprint, same_fingerprint
from jeveval.run.seal import check_seal
from jeveval.run.stage_inputs import load_items, read_stage_finals
from jeveval.score.tasks import outcome
from jeveval.score.threshold import dev_complete
from jeveval.types import RunContext, StageData, ThresholdFile


def configuration(root, model, task, base_url=None) -> RunContext:
    root = Path(root).resolve()
    model, task_path = inside(root, model), inside(root, task)
    cfg, task = load_model_config(model), load_taskspec(task_path)
    if base_url is not None:
        cfg = validate_model_config({**cfg.to_dict(), "base_url": base_url}, model.stem)
        if isinstance(cfg, list):
            raise ValueError("invalid base URL")
    for value in (cfg.id, task.set, task.variant):
        identifier(value)
    plan = read_split_plan(root / "configs/splits" / f"{task.set}.json")
    if plan.set != task.set or check_split_plan(plan):
        raise ValueError("invalid split plan")
    b1 = read_b1_config(root / "configs/tasks/b1.yaml")
    policy = read_retry_policy(root / "configs/policy.yaml")
    return RunContext(root=root, model_path=model, task_path=task_path,
                      cfg=cfg, task=task, plan=plan, b1=b1, policy=policy)


def fingerprint(ctx, run_id, started_at):
    return build_fingerprint(root=ctx.root, run_id=identifier(run_id),
        model_cfg_path=ctx.model_path, task_path=ctx.task_path,
        set_name=ctx.task.set, variant=ctx.task.variant, started_at=started_at)


def restore(root, run_dir) -> RunContext:
    directory = inside(root, run_dir)
    saved = run_files.read_json(directory / "fingerprint.json")
    inputs = saved["inputs"]
    ctx = configuration(root, inputs["model_cfg_path"], inputs["task_path"])
    current = fingerprint(ctx, inputs["run_id"], saved["started_at"])
    if not same_fingerprint(saved, current):
        raise ValueError("frozen inputs differ")
    return replace(ctx, directory=directory, fingerprint=saved)


def identity(ctx):
    if ctx.fingerprint is None or ctx.directory is None:
        raise ValueError("context is not restored")
    return {key: ctx.fingerprint[key] for key in ("model", "set", "variant", "run_id")}


def check_identity(ctx, data):
    if any(data[key] != value for key, value in identity(ctx).items()):
        raise ValueError("result identity mismatch")


def stage(ctx, name) -> StageData:
    if ctx.directory is None:
        raise ValueError("context is not restored")
    if name == "extra" and name not in stage_names(ctx.task.set):
        raise ValueError("extra only supported for FunctionChat")
    finals, warnings = read_stage_finals(ctx.directory, name)
    ids = [f.logical_id for f in finals]
    expected = ctx.plan.extra if name == "extra" else [
        ctx.plan.representative[g] for g in getattr(ctx.plan, name)]
    if (name == "dev" and dev_complete(ids, ctx.plan)) or set(ids) != set(expected):
        raise ValueError("stage is incomplete")
    if not run_files.exists(ctx.directory / name / "final.jsonl"):
        raise ValueError("stage final missing")
    items = load_items(root=ctx.root, task_path=ctx.task_path, stage=name)
    by_id = {f"{i.set}:{i.group_id}:{i.item_id}": i for i in items}
    if set(by_id) != set(expected):
        raise ValueError("stage Items differ from split")
    rows = [outcome(f, by_id[f.logical_id], name) for f in finals]
    return StageData(finals=finals, items=by_id, outcomes=rows, warnings=warnings)


def primary_variant(ctx):
    return set_primary_variant(ctx.root, entry(ctx.root, ctx.task.set))


def completed(root, run_dir):
    """compare/archive 공통 선행: 불변 입력·단계 완료·threshold identity·봉인."""
    ctx = restore(root, run_dir)
    names = stage_names(ctx.task.set)
    stages = {name: stage(ctx, name) for name in names}
    threshold = run_files.read_json(ctx.directory / "threshold.json", ThresholdFile)
    check_identity(ctx, threshold.to_dict())
    if not run_files.exists(ctx.directory / "test/seal.json") or check_seal(ctx.directory):
        raise ValueError("valid seal required")
    return ctx, stages, threshold
