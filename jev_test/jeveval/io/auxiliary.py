"""무엇: 보조 파일 격리 읽기 · 입력: 역사 경로/증거 · 출력: aux 상태 · 계약 §7-4c."""

from jeveval.io import run_files
from jeveval.io.paths import inside
from jeveval.score.selective_artifact import validate


def selective(root, directory, artifacts, hashes):
    """보조 오류를 주 역사 errors에 전파하지 않는다."""
    try:
        path = inside(root, directory / "selective.json")
        if not path.exists():
            return dict(status="missing", value=None)
        value = run_files.read_json(path)
        validate(value, artifacts["fingerprint.json"], hashes, artifacts["risk.json"])
        return dict(status="valid", value=value)
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        return dict(status="invalid", value=None)
