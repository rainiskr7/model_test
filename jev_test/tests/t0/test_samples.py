"""대상 해시의 입력 범위와 서버/참조 관측 봉투 구분."""

from dataclasses import replace
from hashlib import sha256

import pytest

from jeveval.t0.request import canonical_bytes
from jeveval.t0.samples import observation, targets
from jeveval.types.t0 import T0Observation
from jeveval.types.t0_io import T0Input


@pytest.fixture
def row():
    body = dict(model="reference-name", state="state", questions={"z": {"type": "noul"}}, images=["image"])
    return T0Input("c", {**body, "model": "server-name"}, body, "r" * 64, "s" * 64, "f" * 64, None, None)


def test_target_hash_uses_state_question_images_only(row):
    expected = sha256(canonical_bytes(dict(state="state", question={"type": "noul"}, images=["image"]))).hexdigest()
    assert targets(row) == {"z": expected}
    assert targets(replace(row, reference_body={**row.reference_body, "model": "other"})) == targets(row)
    for key, value in [("state", "changed"), ("images", []), ("questions", {"z": {"type": "choice"}})]:
        assert targets(replace(row, reference_body={**row.reference_body, key: value})) != targets(row)


@pytest.mark.parametrize("reference,envelope", [(False, "s" * 64), (True, "f" * 64)])
def test_observation_selects_envelope_and_preserves_failure(row, reference, envelope):
    result = observation(row, "i" * 64, None, "raw", reference=reference,
                         error="timeout", length_status="truncated")
    assert result == T0Observation("c", "i" * 64, "r" * 64, envelope, None, "raw", "timeout", "truncated")
