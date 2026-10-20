"""입력: 합성 MTVQA 응답·singleton gold. 출력: lmms 규칙·경계 사례 검증."""

from copy import deepcopy

import pytest

from shared.multimodal.publish.adapters_accuracy import _mtvqa_match
from shared.multimodal.rescore.manifest import build_manifest
from shared.multimodal.rescore.mtvqa_lmms import lmms_match, score


def mtvqa_case(answer="서울", response="서울입니다"):
    raw = [{"id": "KR_0", "lang": "KR", "image": {"bytes": b"image"},
            "qa_pairs": [{"question": "도시?", "answer": answer}]}]
    rows = [{"id": "KR_0", "row_idx": 0, "qa_idx": 0, "question": "도시?",
             "gold": [answer], "response": response, "error": None, "correct": False}]
    return rows, build_manifest("mtvqa_kr", raw, {"fixture": True})


@pytest.mark.parametrize("prediction,gold,expected", [
    (" SEOUL. ", "seoul", True),
    ("1.25", "125", True),
    ("서울입니다", "서울", True),
    ("대한", "대한민국", False),
    ("Ａ", "A", False),
    ("<think>서울</think>부산", "서울", True),
    ("대 한 민 국", "대한민국", False),
    ("", "서울", False),
    ("anything", " . ", False),
    ({"error": "서울"}, "서울", False),
])
def test_pinned_spec_rule_cases(prediction, gold, expected):
    assert lmms_match(prediction, gold) is expected


def test_rule_is_not_monotonic_relative_to_existing_match():
    assert _mtvqa_match("대한", "대한민국") is True
    assert lmms_match("대한", "대한민국") is False
    assert _mtvqa_match("서울입니다", "서울") is False
    assert lmms_match("서울입니다", "서울") is True


def test_singleton_unwrap_and_input_unchanged():
    rows, manifest = mtvqa_case()
    before = deepcopy((rows, manifest))
    result = score(rows, manifest)
    assert result["accepted"] is True
    assert (result["correct"], result["accuracy"], result["stored_correct"]) == (1, 1, 0)
    assert result["item_scores"][0]["image_id"] == "KR_0"
    assert (rows, manifest) == before


@pytest.mark.parametrize("gold", [[], ["서울", "부산"], "서울", [None]])
def test_non_singleton_string_gold_rejected(gold):
    rows, manifest = mtvqa_case()
    rows[0]["gold"] = gold
    result = score(rows, manifest)
    assert result["accepted"] is False
    assert result["correct"] is None
    assert result["issues"][0]["reason"] == "singleton_string_gold_required"


def test_empty_normalized_gold_is_counted_failure():
    rows, manifest = mtvqa_case(answer=" . ")
    result = score(rows, manifest)
    assert result["accepted"] is True
    assert (result["correct"], result["empty_gold"]) == (0, 1)


@pytest.mark.parametrize("response", [{"error": "서울"}, "서울"])
def test_error_never_matches_even_when_gold_appears(response):
    rows, manifest = mtvqa_case(response=response)
    rows[0]["error"] = "offline failure"
    result = score(rows, manifest)
    assert result["accepted"] is True
    assert (result["correct"], result["errored"]) == (0, 1)


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "id", "position", "gold", "response"])
def test_identity_and_response_validation(mutation):
    rows, manifest = mtvqa_case()
    if mutation == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif mutation == "missing":
        rows.clear()
    else:
        field, value = {"id": ("id", "KR_9"), "position": ("row_idx", 1),
                        "gold": ("gold", ["부산"]), "response": ("response", None)}[mutation]
        rows[0][field] = value
    assert score(rows, manifest)["accepted"] is False
