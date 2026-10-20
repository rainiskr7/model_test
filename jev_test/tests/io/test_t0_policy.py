"""T0 정책 파일 값과 바이트 해시 로딩."""

from pathlib import Path

import pytest

from jeveval.io.hashes import sha256_file
from jeveval.io.t0_policy import read_t0_policy
from jeveval.types.t0_io import T0Policy
from tests.run.file_support import put_yaml

REPO = Path(__file__).resolve().parents[2]


def test_repository_t0_policy_values_and_hash():
    path = REPO / "configs/t0/tolerance_v1.yaml"
    batches = ["batch_1", "batch_4", "batch_8"]
    variants = {"clef": batches, "clef_flash": batches, "pplx_v1": batches,
                "pplx_v1_1": ["single", "eight_0", "eight_7", "seventeen_0", "seventeen_7",
                              "seventeen_8", "seventeen_15", "seventeen_16"]}
    assert read_t0_policy(path) == T0Policy(5, .02, variants, sha256_file(path))


def test_t0_policy_loader_joins_errors(tmp_path):
    path = tmp_path / "policy.yaml"
    put_yaml(path, dict(schema="t0_tolerance_policy/1", repeats=0, max_variation=-1,
                        variants={"pplx_v1_1": ["single"]}))
    with pytest.raises(ValueError) as exc:
        read_t0_policy(path)
    assert str(exc.value) == ("repeats must be a positive integer; "
                              "max_variation must be a nonnegative finite number")
