"""무엇: 질문 위험 명령 · 입력: 완료 run · 출력: 등록/탐색/손상 · 계약 판 5 보정 2 §7-4b."""

from jeveval.io import analysis, history as history_io, run_files
from jeveval.io.paths import inside, identifier
from jeveval.io import question_registration as evidence_io
from jeveval.run import context, history_check, history_stage, question_registration
from jeveval.score.question_outcomes import observations
from jeveval.score.question_risk import calculate, thresholds


def _history(root, run_dir):
    saved = history_io.read(root, run_dir)
    if history_check.check(saved).status != "verified_complete":
        raise ValueError("verified complete history required")
    stages = {s: history_stage.restore(root, saved, s) for s in ("dev", "test")}
    fp = saved.artifacts["fingerprint.json"]
    return {k: fp[k] for k in question_registration.IDENTITY}, saved.directory, stages


def run(*, root, run_dir, history=False):
    e = evidence_io.read(root, run_dir)
    status = "exploratory" if history else question_registration.check(e)
    manifest, digest = (analysis.policy(root) if history or status == "exploratory" else
                        (e["policy"], e["manifest_sha256"]))
    name = analysis.MANIFEST if history or status == "exploratory" else e["manifest"]
    if history:
        identity, directory, stages = _history(root, run_dir)
    elif status == "registration_damaged":
        identity = {k: identifier(e["artifacts"]["fingerprint.json"][k]) for k in question_registration.IDENTITY}
        directory, stages = inside(root, run_dir), None
    else:
        ctx, stages, _ = context.completed(root, run_dir)
        identity, directory = context.identity(ctx), ctx.directory
    values = {}
    if stages is not None:
        rows = {s: observations(stages[s].finals, stages[s].items, s) for s in ("dev", "test")}
        if status == "registered":
            status = question_registration.check(e, thresholds(rows["dev"]))
        if status != "registration_damaged":
            frozen = e["artifacts"]["question_threshold.json"]["by_question"] if status == "registered" else None
            values = calculate(rows["dev"], rows["test"], frozen)
    value = dict(schema="question_risk/1", **identity,
                 registration=dict(status=status, manifest=name, manifest_sha256=digest),
                 claims=None if manifest is None else manifest["claims"], **values)
    if history and run_files.exists(directory / "question_risk.json"):
        raise ValueError("historical question risk artifact already exists")
    run_files.write_json(directory / "question_risk.json", value)
    return dict(ok=True, registration=status)
