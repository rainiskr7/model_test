"""무엇: 격리 Python의 import 경로 · 입력: 테스트 위치 · 출력: sys.path · 계약 §8-4 작업 1."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
