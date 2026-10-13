"""무엇: 명령 입력 복원 · 입력: root/run 경로 · 출력: 검증된 설정/기록 · 계약 §8-6 E/F/M."""

from pathlib import Path
from types import SimpleNamespace

from jeveval.contract.model_config import validate_model_config
from jeveval.data.split import check_split_plan
from jeveval.io import run_files
from jeveval.io.config import load_taskspec, read_yaml
from jeveval.io.models import load_model_config
from jeveval.io.splits import read_split_plan
from jeveval.io.tasks import read_b1_config
from jeveval.run.fingerprint import build_fingerprint, same_fingerprint
from jeveval.run.layout import identifier
from jeveval.run.stage_inputs import load_items, read_stage_finals
from jeveval.score.tasks import outcome
from jeveval.score.threshold import dev_complete


def inside(root, path):
    root = Path(root).resolve()
    result = (root / path).resolve()
    if not result.is_relative_to(root):
        raise ValueError("path outside repository")
    return result


def configuration(root, model, task, base_url=None):
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
    return SimpleNamespace(root=root, model_path=model, task_path=task_path,
                           cfg=cfg, task=task, plan=plan, b1=b1)


def fingerprint(ctx, run_id, started_at):
    return build_fingerprint(root=ctx.root, run_id=identifier(run_id),
        model_cfg_path=ctx.model_path, task_path=ctx.task_path,
        set_name=ctx.task.set, variant=ctx.task.variant, started_at=started_at)


def restore(root, run_dir):
    directory = inside(root, run_dir)
    saved = run_files.read_json(directory / "fingerprint.json")
    inputs = saved["inputs"]
    ctx = configuration(root, inputs["model_cfg_path"], inputs["task_path"])
    current = fingerprint(ctx, inputs["run_id"], saved["started_at"])
    if not same_fingerprint(saved, current):
        raise ValueError("frozen inputs differ")
    ctx.directory, ctx.fingerprint = directory, saved
    return ctx


def identity(ctx):
    return {key: ctx.fingerprint[key] for key in ("model", "set", "variant", "run_id")}


def check_identity(ctx, data):
    if any(data[key] != value for key, value in identity(ctx).items()):
        raise ValueError("result identity mismatch")


def stage(ctx, name):
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
    return SimpleNamespace(finals=finals, items=by_id, outcomes=rows, warnings=warnings)


def primary_variant(ctx):
    def entries(value):
        if isinstance(value, dict):
            if value.get("id") == ctx.task.set:
                yield value
            for child in value.values():
                yield from entries(child)
        elif isinstance(value, list):
            for child in value:
                yield from entries(child)
    matches = list(entries(read_yaml(ctx.root / "configs/datasets.yaml")))
    if len(matches) != 1:
        raise ValueError("dataset identity missing or duplicated")
    mapping = matches[0].get("map", {})
    if "primary_variant" in mapping:
        return identifier(mapping["primary_variant"])
    variants = {task.variant for path in sorted((ctx.root / "configs/tasks").glob("*.yaml"))
                if path.stem != "b1" for task in [load_taskspec(path)] if task.set == ctx.task.set}
    if len(variants) != 1:
        raise ValueError("SPEC_AMBIGUOUS: primary variant")
    return variants.pop()


def file_info(path):
    stat = Path(path).stat()
    return stat.st_size, stat.st_mtime
