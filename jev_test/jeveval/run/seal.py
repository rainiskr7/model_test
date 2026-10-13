"""무엇: 시험 전 봉인·resume 대조 · 입력: 실행 경로·시각 · 출력: 봉인/불일치 · 계약 §5-7·§8-6 A."""

from pathlib import Path

from jeveval.io import run_files
from jeveval.io.hashes import sha256_file


def write_seal(run_dir, *, now) -> dict:
    """원본 바이트 해시를 첫 시험 전에 기록하며 기존 봉인을 덮어쓰지 않는다."""
    run_dir = Path(run_dir)
    path = run_dir / "test/seal.json"
    if run_files.exists(path):
        raise ValueError("seal already exists")
    if not run_files.exists(run_dir / "threshold.json"):
        raise ValueError("threshold is required")
    try:
        seal = dict(threshold_sha256=sha256_file(run_dir / "threshold.json"),
                    dev_final_sha256=sha256_file(run_dir / "dev/final.jsonl"), sealed_at=now)
    except OSError:
        raise ValueError("seal input unavailable") from None
    run_files.make_directory(path.parent)
    run_files.write_json(path, seal)
    return seal


def check_seal(run_dir) -> list[str]:
    """봉인이 없으면 빈 목록, 있으면 누락 파일도 해당 해시 불일치로 반환한다."""
    run_dir = Path(run_dir)
    path = run_dir / "test/seal.json"
    if not run_files.exists(path):
        return []
    seal = run_files.read_json(path)
    if not isinstance(seal, dict):
        raise ValueError("invalid seal")
    errors = []
    for key, name in (("threshold_sha256", "threshold.json"),
                      ("dev_final_sha256", "dev/final.jsonl")):
        try:
            matches = seal.get(key) == sha256_file(run_dir / name)
        except OSError:
            matches = False
        if not matches:
            errors.append(key)
    return errors
