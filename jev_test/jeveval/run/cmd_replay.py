"""무엇: 출처 attempts 복사 명령 · 입력: 모델/task/출처/새 run · 출력: replay/1 · 계약 §5-5c."""

from datetime import datetime, timezone
from hashlib import sha256

from jeveval.contract.stages import supports_extra
from jeveval.io import records, run_files
from jeveval.io.paths import identifier, inside
from jeveval.run import context, replay_check, stage_inputs
from jeveval.run.fingerprint import same_fingerprint
from jeveval.run.layout import run_dir as result_dir
from jeveval.run.plan_calls import plan_calls
from jeveval.run.resume_check import check_resume


def _metadata(ctx, source, fp, fp_bytes, payload, stamp, reason):
    return dict(schema="replay/1", source_run_dir=source.relative_to(ctx.root).as_posix(),
                source_run_id=fp["run_id"], source_code_sha256=fp["code_sha256"], source_env=fp["env"],
                source_fingerprint_sha256=sha256(fp_bytes).hexdigest(),
                source_attempts_sha256=sha256(payload).hexdigest(), source_attempts_nbytes=len(payload),
                copied_at=stamp, reason=reason)


def _target(ctx, directory, stage, current, metadata):
    """기존 final은 항상 거부하고 동일 provenance의 복사 중단만 복구한다."""
    final = inside(ctx.root, stage_inputs.final_path(directory, stage))
    attempts = inside(ctx.root, stage_inputs.attempts_path(directory, stage))
    marker = inside(ctx.root, directory / stage / "replay.json")
    fp_path = inside(ctx.root, directory / "fingerprint.json")
    if run_files.exists(final):
        raise ValueError("target final already exists")
    if run_files.exists(fp_path) and not same_fingerprint(run_files.read_json(fp_path), current):
        raise ValueError("target fingerprint differs")
    if run_files.exists(marker):
        saved = run_files.read_json(marker)
        if (not isinstance(saved, dict) or saved.keys() != metadata.keys()
                or any(saved[k] != v for k, v in metadata.items() if k != "copied_at")):
            raise ValueError("replay provenance differs")
        if run_files.exists(attempts) and run_files.file_sha256(attempts) != metadata["source_attempts_sha256"]:
            raise ValueError("target attempts differ")
        return saved
    if run_files.exists(attempts):
        raise ValueError("target attempts already exists")
    return metadata


def _source(ctx, source, stage, current):
    fp_path = inside(ctx.root, source / "fingerprint.json")
    attempt_path = inside(ctx.root, stage_inputs.attempts_path(source, stage))
    fp_bytes, fp = run_files.read_bytes(fp_path), run_files.read_json(fp_path)
    if replay_check.compatible(fp, current):
        raise ValueError("source fingerprint incompatible")
    identifier(fp["run_id"])
    if fp["run_id"] == current["run_id"]:
        raise ValueError("source run_id must differ")
    payload = run_files.read_bytes(attempt_path)
    attempts, warnings = records.read_attempts(attempt_path)
    if replay_check.complete_attempts(attempts, warnings):
        raise ValueError("source attempts incomplete")
    items = stage_inputs.load_items(root=ctx.root, task_path=ctx.task_path, stage=stage)
    plans = [p for item in items for p in plan_calls(item, ctx.task, ctx.cfg, ctx.b1)]
    if check_resume(plans, attempts, [], ctx.policy.max_attempts):
        raise ValueError("source attempts do not match plans")
    return fp, fp_bytes, payload, attempt_path


def run(*, root, model, task, stage, run_id, source_run_dir, results="results", reason=None):
    if replay_check.check_reason(reason):
        raise ValueError("invalid replay reason")
    ctx = context.configuration(root, model, task)
    directory = result_dir(inside(ctx.root, results), ctx.cfg.id, run_id, ctx.task.set, ctx.task.variant)
    destination = inside(ctx.root, stage_inputs.attempts_path(directory, stage))
    source = inside(ctx.root, source_run_dir)
    if source == directory:
        raise ValueError("source must differ from target")
    if stage == "extra" and not supports_extra(ctx.task.set):
        raise ValueError("extra only supported for FunctionChat")
    if ctx.task.variant == "actions_only" and ctx.cfg.question_scoring == "separate":
        raise ValueError("derived variants cannot be replayed")
    stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    current = context.fingerprint(ctx, run_id, stamp)
    fp, fp_bytes, payload, attempt_path = _source(ctx, source, stage, current)
    metadata = _metadata(ctx, source, fp, fp_bytes, payload, stamp, reason)
    metadata = _target(ctx, directory, stage, current, metadata)
    run_files.json_bytes(metadata)
    run_files.make_directory(destination.parent)
    run_files.write_json(inside(ctx.root, destination.parent / "replay.json"), metadata)
    run_files.copy_bytes(attempt_path, destination)
    return dict(ok=True, replay=True, warnings=[])
