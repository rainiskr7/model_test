"""무엇: 확신 변형 명령 · 입력: run/threshold 또는 risk/history · 출력: 보조 파일 · 계약 §7-4d."""

from jeveval.io import analysis_artifacts, history as history_io, run_files, variant_policy
from jeveval.io.hashes import sha256_file
from jeveval.run import context, history_check, history_stage, variant_calculation, variant_registration


def _threshold(root, directory):
    ctx = context.restore(root, directory)
    e = analysis_artifacts.read(root, ctx.directory)
    if e["started"] or e["errors"] or e["manifest"] is None:
        raise ValueError("declared policy and unstarted test required")
    ordinary = run_files.read_json(ctx.directory / "threshold.json")
    context.check_identity(ctx, ordinary)
    if ordinary["dev_input"]["sha256"] != e["hashes"]["dev/final.jsonl"]:
        raise ValueError("ordinary threshold dev differs")
    dev = context.stage(ctx, "dev")
    if dev.warnings:
        raise ValueError("complete undamaged dev required")
    value = dict(schema="variant_threshold/1", **context.identity(ctx),
        fingerprint_sha256=e["hashes"]["fingerprint.json"], manifest=e["manifest"],
        manifest_sha256=e["manifest_sha256"], dev_final_sha256=e["hashes"]["dev/final.jsonl"],
        threshold_sha256=e["hashes"]["threshold.json"], **variant_calculation.development(dev))
    analysis_artifacts.write_new(ctx.directory, "variant_threshold.json", value)
    return dict(ok=True)


def _inputs(root, directory, historical):
    if not historical:
        ctx, stages, _ = context.completed(root, directory)
        return context.identity(ctx), ctx.directory, stages
    saved = history_io.read(root, directory)
    if history_check.check(saved).status != "verified_complete":
        raise ValueError("verified complete history required")
    if any(f.derived_from is not None for s in saved.stages for f in s.finals):
        raise ValueError("derived variant historical analysis unsupported")
    stages = {s: history_stage.restore(root, saved, s) for s in ("dev", "test")}
    return {k: saved.artifacts["fingerprint.json"][k] for k in variant_registration.IDENTITY}, saved.directory, stages


def run(*, root, run_dir, mode="risk", history=False):
    if mode == "threshold":
        if history:
            raise ValueError("history cannot register thresholds")
        return _threshold(root, run_dir)
    if mode != "risk":
        raise ValueError("unknown variant command")
    identity, directory, stages = _inputs(root, run_dir, history)
    e = analysis_artifacts.read(root, directory)
    status = "exploratory" if history else variant_registration.check(e)
    policy = variant_calculation.development(stages["dev"])
    if status == "registered":
        status = variant_registration.check(e, policy)
        policy = e["artifacts"]["variant_threshold.json"]
    manifest, digest = (variant_policy.MANIFEST, variant_policy.policy(root)[1]) if status == "exploratory" else (
        e["manifest"], e["manifest_sha256"])
    value = dict(schema="score_variants/1", **identity,
        registration=dict(status=status, manifest=manifest, manifest_sha256=digest),
        inputs={p: sha256_file(directory / p) for p in ("dev/final.jsonl", "test/final.jsonl")},
        cells={} if status == "registration_damaged" else variant_calculation.trial(stages["test"], policy))
    if history:
        analysis_artifacts.write_new(directory, "score_variants.json", value)
    else:
        run_files.write_json(directory / "score_variants.json", value)
    return dict(ok=True, registration=status)
