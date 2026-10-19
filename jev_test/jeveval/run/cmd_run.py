"""무엇: 실행/파생 명령 · 입력: 모델/task/단계 · 출력: 기록/집계 · 계약 §5·⑥b R1–R7."""

from dataclasses import replace
from datetime import datetime, timezone
import os
import time
from uuid import uuid4

from jeveval.client import http
from jeveval.contract.model_config import missing_for_run
from jeveval.io import derived_stage, records, run_files, t0
from jeveval.io.paths import inside
from jeveval.run import context, derived_resume, executor, gate, stage_inputs
from jeveval.run.derive import derive_stage
from jeveval.run.encoders import measurer_for
from jeveval.run.layout import run_dir as result_dir
from jeveval.run.plan_calls import plan_calls
from jeveval.run.resume_check import check_resume


def _common(fp):
    result = {key: fp[key] for key in ("encoder", "tokenizer", "code_sha256",
                                      "dataset_verified", "run_id", "model", "external", "env")}
    result["files"] = {path: digest for path, digest in fp["files"].items()
                       if path != fp["inputs"]["task_path"] or f"configs/sets/{fp['set']}.yaml" in fp["files"]}
    return result


def _derived(ctx, stage, items):
    source = context.restore(ctx.root, ctx.directory.parent / "full")
    if source.task.variant != "full" or source.task.set != ctx.task.set:
        raise ValueError("invalid full variant")
    if _common(source.fingerprint) != _common(ctx.fingerprint):
        raise ValueError("derived source inputs differ")
    full = context.stage(source, stage)
    if {f"{i.set}:{i.group_id}:{i.item_id}" for i in items} != set(full.items):
        raise ValueError("derived Item IDs differ")
    provenance = source.directory.relative_to(ctx.root).as_posix()
    finals = derive_stage(full.finals, list(full.items.values()),
                          [q.id for q in ctx.task.questions], provenance)
    derived_resume.resume_derived(ctx.directory, stage, finals, provenance, allow_tail=True)
    return finals, provenance


def _headers(cfg):
    if cfg.auth_env is None:
        raise ValueError("authentication unavailable")
    value = os.environ.get(cfg.auth_env)
    if not value or any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError("authentication unavailable")
    return {"Authorization": "Bearer " + value}


def _refuse(*args, **kwargs):
    raise RuntimeError("offline run must not send")


def run(*, root, model, task, stage, run_id, base_url=None, results="results",
        check_config=False, measurer=None, post=None, offline=False):
    if offline and base_url is not None:
        raise ValueError("offline and base_url are mutually exclusive")
    ctx = context.configuration(root, model, task, base_url)
    if offline:
        ctx = replace(ctx, cfg=replace(ctx.cfg, base_url="http://replay.invalid"))
        post = _refuse
    directory = result_dir(inside(ctx.root, results), ctx.cfg.id,
                           run_id, ctx.task.set, ctx.task.variant)
    # stage 이름과 셋별 extra 지원은 check-config에서도 검사한다.
    stage_inputs.final_path(directory, stage)
    if stage == "extra" and ctx.task.set != "fc_call_decision":
        raise ValueError("extra only supported for FunctionChat")
    missing = missing_for_run(ctx.cfg, ctx.b1.labels)
    if check_config:
        return dict(ok=not missing, missing_for_run=missing)
    if missing:
        raise ValueError("incomplete run configuration")
    t0.verify_for_run(ctx.root, ctx.model_path)
    derived = ctx.task.variant == "actions_only" and ctx.cfg.question_scoring == "separate"
    headers = {} if derived or offline else _headers(ctx.cfg)
    if not derived and measurer is None:
        measurer = measurer_for(ctx.cfg)
    items = stage_inputs.load_items(root=ctx.root, task_path=ctx.task_path, stage=stage)
    stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    ctx = replace(ctx, directory=directory, fingerprint=context.fingerprint(ctx, run_id, stamp))
    if derived:
        finals, provenance = _derived(ctx, stage, items)
    else:
        plans = [p for item in items for p in plan_calls(item, ctx.task, ctx.cfg, ctx.b1)]
        attempts, _ = records.read_attempts(stage_inputs.attempts_path(directory, stage))
        existing, _ = records.read_finals(stage_inputs.final_path(directory, stage))
        if check_resume(plans, attempts, existing, ctx.policy.max_attempts):
            raise ValueError("resume input mismatch")
    warnings = gate.prepare_stage(run_dir=directory, stage=stage,
        fingerprint=ctx.fingerprint, plan=ctx.plan, now=stamp, root=ctx.root)
    if derived:
        existing = derived_resume.resume_derived(directory, stage, finals, provenance)
        derived_stage.write_derived_stage(directory, stage, finals, provenance, existing)
        return dict(ok=True, derived=True, n_logical=len(finals), warnings=warnings)
    summary = executor.run_stage(items=items, task=ctx.task, cfg=ctx.cfg, b1_config=ctx.b1,
        measurer=measurer, run_dir=directory, stage=stage, post=http.post if post is None else post,
        sleep=time.sleep, session_id=str(uuid4()), policy=ctx.policy, headers=headers, offline=offline)
    return dict(ok=True, **summary.to_dict(), warnings=warnings)
