"""파일럿 RNG의 sample→정렬→choice 순서를 독립 기대값과 비교한다."""

import random
import pytest

from audits.kosgd2_pilot.select_pilot import select
from tests.audits.pilot_support import dialogues


def test_selection_sequence_and_intersections():
    source = dialogues()
    old = [dict(dialogue_id=d["dialogue_id"]) for d in source]
    selected = select(source, old, set(), set())
    rng = random.Random(20261019)
    ids = sorted(rng.sample(sorted(d["dialogue_id"] for d in source), 200))
    expected = [dict(dialogue_id=i, turn_index=rng.choice([0, 2])) for i in ids]
    assert selected == expected == select(list(reversed(source)), list(reversed(old)), set(), set())
    with pytest.raises(ValueError): select(source, old[:-1], set(), set())
    with pytest.raises(ValueError): select(source, old, set(), {ids[0]})
    with pytest.raises(ValueError): select(source, old, {ids[0]}, set())
