"""무엇: 다중 분석 test gate · 입력: run/동결 선언 · 출력: 순서 있는 봉인 계획 · 계약 §7-4d."""

from jeveval.io import analysis_artifacts, run_files
from jeveval.run import context, question_gate, variant_registration, variant_calculation


def prepare(root, directory, fingerprint, now):
    """모든 정책 선검사 후에만 호출자가 question→variant→main 순서로 쓴다."""
    question = question_gate.prepare(root, directory, fingerprint, now)
    writes = [] if question is None else [("test/question_seal.json", question)]
    overlay = f"configs/sets/{fingerprint.get('set')}.yaml"
    artifacts = any(run_files.exists(directory / p) for p in ("variant_threshold.json", "test/variant_seal.json"))
    if overlay not in fingerprint.get("files", {}) and not artifacts:
        return writes
    if root is None:
        raise ValueError("analysis root required")
    e = analysis_artifacts.read(root, directory)
    if variant_registration.check(e) == "exploratory":
        return writes
    ctx = context.restore(root, directory)
    dev = context.stage(ctx, "dev")
    if dev.warnings:
        raise ValueError("undamaged dev required")
    recomputed = variant_calculation.development(dev)
    if variant_registration.check(e, recomputed, sealed=e["started"]) != "registered":
        raise ValueError("variant threshold or seals damaged")
    if not e["started"]:
        writes.append(("test/variant_seal.json", dict(**variant_registration.seal_fields(e), sealed_at=now)))
    return writes
