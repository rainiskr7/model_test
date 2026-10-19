"""무엇: 기존 KoSGD 바이트 앵커 · 입력: 0906d42 해시 · 출력: 불변 · 계약 판 5."""

from hashlib import sha256
from pathlib import Path


def test_original_kosgd_tasks_split_and_all_lists_byte_identical():
    root = Path(__file__).resolve().parents[2]
    for line in (root / "tests/fixtures/phase_a_preserved.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert sha256((root / name).read_bytes()).hexdigest() == digest, name
