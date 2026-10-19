"""무엇: 탐색적 질문 위험 명령 · 입력: 완료 run · 출력: question_risk.json · 계약 §7-4b."""

from jeveval.io import analysis, history as history_io, run_files
from jeveval.run import context, history_check, history_stage
from jeveval.score.question_outcomes import observations
from jeveval.score.question_risk import calculate


def run(*, root, run_dir, history=False):
    manifest, digest = analysis.policy(root)
    if history:
        saved = history_io.read(root, run_dir)
        if history_check.check(saved).status != "verified_complete":
            raise ValueError("verified complete history required")
        stages = {s: history_stage.restore(root, saved, s) for s in ("dev", "test")}
        fp, directory = saved.artifacts["fingerprint.json"], saved.directory
        identity = {k: fp[k] for k in ("model", "set", "variant", "run_id")}
    else:
        ctx, stages, _ = context.completed(root, run_dir)
        identity, directory = context.identity(ctx), ctx.directory
    rows = {s: observations(stages[s].finals, stages[s].items, s) for s in ("dev", "test")}
    value = dict(schema="question_risk/1", **identity,
                 registration=dict(status="exploratory", manifest=analysis.MANIFEST, manifest_sha256=digest),
                 claims=manifest["claims"], **calculate(rows["dev"], rows["test"]))
    run_files.write_json(directory / "question_risk.json", value)
    return dict(ok=True, registration="exploratory")
