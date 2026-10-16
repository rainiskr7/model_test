"""무엇: 로컬 토크나이저 검증·오프라인 로딩 · 입력: 모델 yaml 의 tokenizer {path, files_sha256} · 출력: 폴더 Path·토크나이저 객체 · 계약 §4-3·§8-6 G."""

from pathlib import Path

from jeveval.io.hashes import sha256_file
from jeveval.io.reference import offline_environment


def verified_directory(tokenizer: dict) -> Path:
    """목록 밖 파일은 무시하고 폴더 안의 명시된 파일만 정확히 대조한다."""
    path, hashes = tokenizer.get("path"), tokenizer.get("files_sha256")
    if not isinstance(path, str) or not path or not isinstance(hashes, dict) or not hashes:
        raise ValueError("incomplete tokenizer configuration")
    root = Path(path).resolve()
    if not root.is_dir():
        raise ValueError("tokenizer path must be a directory")
    for name, expected in hashes.items():
        file = (root / name).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            raise ValueError(f"tokenizer file missing or outside directory: {name}")
        if sha256_file(file) != expected:
            raise ValueError(f"tokenizer hash mismatch: {name}")
    return root


def load_offline(directory: Path):
    """오프라인 환경을 켠 뒤 로컬 파일만으로 로드한다. 원격 코드는 실행하지 않는다."""
    offline_environment()
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(str(directory), local_files_only=True, trust_remote_code=False)
