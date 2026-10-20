"""무엇: 첫 test 질문 봉인 준비 · 입력: 읽기 경계와 run · 출력: 봉인 파일 schema · 계약 판 5 보정 2 §7-4b."""

from jeveval.io import question_registration as evidence_io, run_files, analysis
from jeveval.run.question_registration import check, seal_fields


def prepare(root, directory, fingerprint, now):
    """쓰기 전 모두 검사한다. 두 봉인 사이 중단도 재등록으로 복구하지 않는다."""
    declared = ("question_risk" in analysis.declared_paths(root, fingerprint) if root is not None else
                any(p.startswith("configs/analysis/") for p in fingerprint.get("files", {})))
    artifacts = any(run_files.exists(directory / p) for p in
                    ("question_threshold.json", "test/question_seal.json"))
    if not declared and not artifacts:
        return None
    if root is None:
        raise ValueError("registration root required")
    e = evidence_io.read(root, directory)
    if e["started"]:
        if check(e) != "registered":
            raise ValueError("damaged registration at resume")
        return None
    if check(e, sealed=False) != "registered":
        raise ValueError("question threshold required before test")
    return dict(**seal_fields(e), sealed_at=now)
