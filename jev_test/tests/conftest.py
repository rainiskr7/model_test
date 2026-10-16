"""무엇: 격리 Python의 import 경로 · 입력: 테스트 위치 · 출력: sys.path · 계약 §8-4 작업 1."""

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# 기존 합성 표본·fixture 공통 도우미의 절대 import 경로를 유지한다.
sys.path.insert(0, str(ROOT / "tests/types"))
sys.path.insert(0, str(ROOT / "tests/fixtures"))


def pytest_configure(config):
    """io/types의 같은 test_records.py 이름을 독립 모듈로 수집한다."""
    config.option.importmode = "importlib"


@pytest.fixture
def vocab():
    from jeveval.io.datasets import read_label_vocab
    return read_label_vocab(ROOT / "configs/datasets.yaml")


@pytest.fixture
def label_rules(vocab):
    from jeveval.score.labels import rules
    return rules(vocab)


@pytest.fixture
def t0_policy():
    from jeveval.io.t0_policy import read_t0_policy
    return read_t0_policy(ROOT / "configs/t0/tolerance_v1.yaml")
