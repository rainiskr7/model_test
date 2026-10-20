"""무엇: 단계 진입 검사·복구 · 입력: 실행 경로·fingerprint·분할 · 출력: 경고/거부 · 계약 §8-6 A/E."""

from pathlib import Path

from jeveval.io import records, run_files
from jeveval.io.hashes import sha256_file
from jeveval.run.fingerprint import same_fingerprint
from jeveval.run import analysis_gate
from jeveval.run.seal import check_seal, write_seal
from jeveval.run.stage_inputs import attempts_path, final_path, read_stage_finals
from jeveval.score.threshold import dev_complete
from jeveval.types import SplitPlan


def _check(run_dir, stage, fingerprint, plan):
    """모든 읽기/구조 검사를 먼저 수행해 뒤의 tail 복구가 검사를 우회하지 않게 한다."""
    final, attempts = final_path(run_dir, stage), attempts_path(run_dir, stage)
    if run_files.exists(run_dir / "fingerprint.json"):
        if not same_fingerprint(run_files.read_json(run_dir / "fingerprint.json"), fingerprint):
            raise ValueError("fingerprint mismatch")
    warnings = []
    if stage == "test":
        if not run_files.exists(run_dir / "threshold.json"):
            raise ValueError("threshold is required")
        dev, pending = read_stage_finals(run_dir, "dev")
        warnings.extend(pending)
        if dev_complete([r.logical_id for r in dev], plan):
            raise ValueError("dev is incomplete")
        # write_seal에 필요한 읽기도 쓰기 전에 확인한다 (빈 dev 분할 포함).
        sha256_file(run_dir / "threshold.json")
        sha256_file(run_dir / "dev/final.jsonl")
    if stage == "extra":
        test, pending = read_stage_finals(run_dir, "test")
        warnings.extend(pending)
        if {r.logical_id for r in test} != {plan.representative[g] for g in plan.test}:
            raise ValueError("test is incomplete")
    if stage in ("test", "extra") and check_seal(run_dir):
        raise ValueError("seal mismatch")
    # repair_tail의 중간 손상 거부가 fingerprint 쓰기 뒤에 일어나지 않게 한다.
    records.read_attempts(attempts)
    records.read_finals(final)
    return warnings


def prepare_stage(*, run_dir, stage, fingerprint: dict, plan: SplitPlan, now, root=None) -> list[str]:
    """검사 통과 후에만 fingerprint → 해당 단계 tail 복구 → 첫 시험 봉인 순으로 쓴다."""
    run_dir = Path(run_dir)
    try:
        warnings = _check(run_dir, stage, fingerprint, plan)
        seals = analysis_gate.prepare(root, run_dir, fingerprint, now) if stage == "test" else []
        for _, value in seals:
            run_files.json_bytes(value)
        # JSON 직렬화 오류 역시 첫 파일 쓰기 전에 거부한다.
        run_files.json_bytes(fingerprint)
        run_files.json_bytes(dict(sealed_at=now))
    except (ValueError, OSError, TypeError, KeyError, AttributeError):
        raise ValueError("stage preparation checks failed") from None
    run_files.make_directory(final_path(run_dir, stage).parent)
    if not run_files.exists(run_dir / "fingerprint.json"):
        run_files.write_json(run_dir / "fingerprint.json", fingerprint)
    for path in (attempts_path(run_dir, stage), final_path(run_dir, stage)):
        warnings.extend(records.repair_tail(path))
    for name, value in seals:
        run_files.write_json(run_dir / name, value)
    if stage == "test" and not run_files.exists(run_dir / "test/seal.json"):
        write_seal(run_dir, now=now)
    return warnings
