"""입력: 합성 벤치·반복 점수. 출력: 재채점 재사용·문항/이미지 키·반복 평균 검증."""

from copy import deepcopy

import pytest

from shared.multimodal.rescore.manifest import build_manifest
from shared.multimodal.tests.test_rescore_kmmbench_circular_units import circular_case
from shared.multimodal.tests.test_rescore_mtvqa_lmms_units import mtvqa_case
from shared.stats.item_scores import average_runs, index_items, score_items


def dtc_case():
    raw = [{"index": f"document_{i}", "question": f"q{i}", "answer": "A",
            "image": {"bytes": b"image1" if i < 2 else b"image2"}} for i in range(3)]
    rows = [{k: v for k, v in row.items() if k != "image"} | {"correct": i != 1}
            for i, row in enumerate(raw)]
    return rows, build_manifest("k_dtcbench", raw, {"fixture": True})


def test_dtc_string_indices_and_shared_images_with_error_failure():
    rows, manifest = dtc_case()
    rows[2]["error"] = "failed"
    before = deepcopy((rows, manifest))
    result = score_items("k_dtcbench", rows, manifest)
    assert result["metric"] == "kdtc_stored_judgement"
    assert [v["score"] for v in result["items"]] == [1, 0, 0]
    assert result["items"][0]["cluster"] == result["items"][1]["cluster"]
    assert result["items"][0]["cluster"] != result["items"][2]["cluster"]
    assert [v["key"] for v in result["items"]] == ["document_0", "document_1", "document_2"]
    assert (rows, manifest) == before


def test_circular_uses_groups_not_rows_and_reuses_pinned_upstream():
    rows, manifest = circular_case()
    rows[0]["correct"] = False
    result = score_items("k_mmbench", rows, manifest)
    assert result["metric"] == "kmmbench_circular_stored_judgement"
    assert [v["score"] for v in result["items"]] == [0, 1, 1]
    assert result["upstream"]["commit"].startswith("1445ec4")
    assert len(result["items"]) == 3 != len(rows)
    with pytest.raises(ValueError, match="rescore rejected"):
        score_items("k_mmbench", rows[1:], manifest)


def test_mtvqa_reuses_lmms_not_stored_correct_and_keeps_qa_key():
    rows, manifest = mtvqa_case(response="<think>서울</think>부산")
    result = score_items("mtvqa_kr", rows, manifest)
    assert rows[0]["correct"] is False
    assert result["metric"] == "mtvqa_lmms_eval"
    assert result["items"][0]["score"] == 1
    assert result["items"][0]["key"] == "KR_0\t0"
    assert result["upstream"]["commit"].startswith("d8fcb9c")
    rows[0]["gold"].append("부산")
    with pytest.raises(ValueError, match="rescore rejected"):
        score_items("mtvqa_kr", rows, manifest)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "gold", "bool", "bench"])
def test_dtc_rejects_invalid_records(mutation):
    rows, manifest = dtc_case()
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif mutation == "gold":
        rows[0]["answer"] = "B"
    elif mutation == "bool":
        rows[0]["correct"] = None
    with pytest.raises(ValueError):
        score_items("mtvqa_kr" if mutation == "bench" else "k_dtcbench", rows, manifest)


def test_average_repetitions_is_order_independent_and_does_not_mutate():
    rows, manifest = dtc_case()
    first = score_items("k_dtcbench", rows, manifest)
    rows[0]["correct"] = False
    second = score_items("k_dtcbench", rows, manifest)
    before = deepcopy((first, second))
    result = average_runs([first, second, first])
    assert [v["score"] for v in result["items"]] == [2 / 3, 0, 1]
    assert result["repetitions"] == 3
    assert (first, second) == before
    second["items"].reverse()
    assert result == average_runs([second, first, first])


@pytest.mark.parametrize("mutation", ["empty", "items", "cluster", "metric", "version", "upstream"])
def test_average_rejects_incompatible_repetitions(mutation):
    rows, manifest = dtc_case()
    first = score_items("k_dtcbench", rows, manifest)
    second = deepcopy(first)
    if mutation == "items":
        second["items"].pop()
    elif mutation == "cluster":
        second["items"][0]["cluster"] = "different"
    elif mutation != "empty":
        second[mutation] = "different"
    with pytest.raises(ValueError):
        average_runs([] if mutation == "empty" else [first, second])


@pytest.mark.parametrize("mutation", ["empty", "duplicate", "key", "cluster", "nan", "inf", "negative", "bool"])
def test_index_validation(mutation):
    items = [{"key": "one", "cluster": "image", "score": 1}]
    if mutation == "empty":
        items.clear()
    elif mutation == "duplicate":
        items += items[:]
    elif mutation in ("key", "cluster"):
        items[0][mutation] = ""
    else:
        items[0]["score"] = {"nan": float("nan"), "inf": float("inf"),
                             "negative": -1, "bool": True}[mutation]
    with pytest.raises(ValueError):
        index_items(items)
