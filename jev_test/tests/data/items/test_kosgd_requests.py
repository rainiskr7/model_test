"""정답 없는 Request 입구의 state/질문/USER 경계 검사."""

from pathlib import Path
import json
import pytest
from jeveval.data.items.kosgd_requests import build
from jeveval.io.config import load_taskspec
from jeveval.io.tasks import read_lists
from jeveval.types.kosgd_requests import DialoguePrefix

ROOT = Path(__file__).resolve().parents[3]


def test_request_contains_only_projected_dialogue_and_questions():
    task = load_taskspec(ROOT / "configs/tasks/kosgd2_full.yaml")
    lists = read_lists(ROOT / "configs/tasks/lists")
    p = DialoguePrefix("d", 0, (("USER", "synthetic"),))
    r = build(p, lists["kosgd_catalog"], task, lists["catalog_intents_plus_none"], model="synthetic")
    assert len(r.questions) == 13
    assert set(json.loads(r.state)["dialogue"][0]) == {"speaker", "utterance"}
    with pytest.raises(ValueError):
        build(DialoguePrefix("d", 0, (("SYSTEM", "x"),)), [], task, {}, model="x")
