"""입력: 합성 순환 행·manifest. 출력: C1의 집계·거부 결과 검증."""

from copy import deepcopy

import pytest

from shared.multimodal.rescore.kmmbench_circular import score
from shared.multimodal.rescore.manifest import build_manifest


def circular_case(sizes=(2, 3, 4)):
    source, records = [], []
    for group, size in enumerate(sizes, 1):
        for offset in range(size):
            index = group + offset * 1_000_000
            source.append({"index": index, "question": f"q{group}", "answer": "A",
                           "image": {"bytes": f"image{group}".encode()},
                           "A": "a", "B": "b", "C": "c", "D": "d"})
            records.append({"index": index, "question": f"q{group}", "answer": "A",
                            "correct": True, "error": None})
    return records, build_manifest("k_mmbench", source, {"fixture": True})


def test_all_expected_variants_pass_including_four_options_three_copies():
    rows, manifest = circular_case()
    result = score(rows, manifest)
    assert result["accepted"] is True
    assert (result["groups"], result["passed"], result["accuracy"]) == (3, 3, 1)
    assert result["variants"] == {"2": 1, "3": 1, "4": 1}
    assert manifest["counts"]["four_options_three_variants"] == 1
    assert result["incomplete_groups"] == 0
    assert all(g["score"] <= g["row_mean"] for g in result["group_scores"])


@pytest.mark.parametrize("field,value", [("correct", False), ("error", "offline failure")])
def test_wrong_or_error_fails_whole_group(field, value):
    rows, manifest = circular_case()
    rows[0][field] = value
    result = score(rows, manifest)
    assert result["accepted"] is True
    assert result["passed"] == 2
    assert result["accuracy"] == 2 / 3
    assert result["group_scores"][0]["score"] == 0


@pytest.mark.parametrize("remove", [0, 1])
def test_base_or_middle_variant_missing_rejected(remove):
    rows, manifest = circular_case((3,))
    rows.pop(remove)
    result = score(rows, manifest)
    assert result["accepted"] is False
    assert result["accuracy"] is None
    assert result["incomplete_groups"] == 1
    assert result["group_scores"][0]["score"] == 0
    assert {"reason": "missing_items", "count": 1} in result["issues"]


@pytest.mark.parametrize("change", ["duplicate", "extra", "none", "string", "integer", "index_string", "gold", "shape"])
def test_invalid_records_are_explicitly_rejected(change):
    rows, manifest = circular_case()
    if change == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif change == "extra":
        rows.append({**rows[0], "index": 999})
    elif change in ("none", "string", "integer"):
        rows[0]["correct"] = {"none": None, "string": "true", "integer": 1}[change]
    elif change == "index_string":
        rows[0]["index"] = str(rows[0]["index"])
    elif change == "gold":
        rows[0]["answer"] = "B"
    else:
        rows[0] = None
    result = score(rows, manifest)
    assert result["accepted"] is False
    assert result["accuracy"] is None and result["issues"]


def test_input_unchanged_and_group_weighted_inequality_not_row_weighted():
    rows, manifest = circular_case((2, 4))
    for row in rows[2:]:
        row["correct"] = False
    before = deepcopy((rows, manifest))
    result = score(rows, manifest)
    assert result["accuracy"] == 1 / 2
    assert result["row_accuracy"] == 2 / 6
    assert all(g["score"] <= g["row_mean"] for g in result["group_scores"])
    assert (rows, manifest) == before
