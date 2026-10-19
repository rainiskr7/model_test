"""무엇: 개발 질문 임계값 명령 · 입력: 등록된 현재 run · 출력: question_threshold/1 · 계약 판 5 보정 2 §7-4b."""

from jeveval.io import question_registration as evidence_io, run_files
from jeveval.run import context
from jeveval.score.question_outcomes import observations
from jeveval.score.question_risk import thresholds
from jeveval.score.threshold import TAUS


def run(*, root, run_dir):
    ctx = context.restore(root, run_dir)
    e = evidence_io.read(root, ctx.directory)
    if e["started"] or run_files.exists(ctx.directory / "question_threshold.json"):
        raise ValueError("question threshold already frozen or test started")
    if e["errors"] or e["manifest"] is None or e["policy"]["status"] != "registered":
        raise ValueError("registered fingerprint required")
    ordinary = run_files.read_json(ctx.directory / "threshold.json")
    context.check_identity(ctx, ordinary)
    if ordinary["dev_input"]["sha256"] != e["hashes"]["dev/final.jsonl"]:
        raise ValueError("ordinary threshold dev differs")
    dev = context.stage(ctx, "dev")
    if dev.warnings:
        raise ValueError("complete undamaged dev required")
    values = thresholds(observations(dev.finals, dev.items, "dev"))
    value = dict(schema="question_threshold/1", **context.identity(ctx),
                 fingerprint_sha256=e["hashes"]["fingerprint.json"], manifest=e["manifest"],
                 manifest_sha256=e["manifest_sha256"], dev_final_sha256=e["hashes"]["dev/final.jsonl"],
                 questions=sorted(values), taus=list(TAUS), by_question=values)
    run_files.write_json(ctx.directory / "question_threshold.json", value)
    return dict(ok=True)
