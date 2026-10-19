"""라벨 없는 prefix는 frozen이며 파일럿 정체성을 갖는다."""

from dataclasses import FrozenInstanceError
import pytest
from jeveval.types.kosgd_requests import DialoguePrefix


def test_frozen_prefix_identity():
    p = DialoguePrefix("d", 0, (("USER", "hello"),))
    assert p.logical_id == "kosgd2_pilot:d:0"
    with pytest.raises(FrozenInstanceError): p.turn_index = 2
