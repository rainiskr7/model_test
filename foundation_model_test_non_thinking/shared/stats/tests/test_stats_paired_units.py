"""입력: 기대값을 손으로 계산할 수 있는 이미지 묶음. 출력: C3 bootstrap 불변식 검증."""

from copy import deepcopy
import random

import pytest

from shared.stats.paired import INTERPRETATION, bootstrap, percentile, validate_pair


def pair_case():
    common = {"cohort": ["K-DTCBench", "full", "fingerprint"], "metric": "fixture",
              "version": 1, "upstream": None, "repetitions": 3}
    a = {**common, "items": [
        {"key": "a", "cluster": "one", "score": 1},
        {"key": "b", "cluster": "one", "score": 1},
        {"key": "c", "cluster": "two", "score": 0}]}
    b = {**common, "items": [
        {"key": "a", "cluster": "one", "score": 0},
        {"key": "b", "cluster": "one", "score": 0},
        {"key": "c", "cluster": "two", "score": 1}]}
    return a, b


def test_seed_reproducibility_order_invariance_no_global_rng_or_input_mutation():
    a, b = pair_case()
    before, rng_state = deepcopy((a, b)), random.getstate()
    result = bootstrap(a, b, seed=42, resamples=100)
    assert result == bootstrap(a, b, seed=42, resamples=100)
    assert (a, b) == before and random.getstate() == rng_state
    a["items"].reverse()
    b["items"] = b["items"][1:] + b["items"][:1]
    assert bootstrap(a, b, seed=42, resamples=100) == result
    assert result["ci95"] == [-1, 1]
    assert result["difference"] == 1 / 3
    assert result["interpretation"] == INTERPRETATION


def test_same_model_is_exactly_zero_in_every_draw():
    a, _ = pair_case()
    result = bootstrap(a, deepcopy(a), seed=7, resamples=100)
    assert result["difference"] == 0 and result["ci95"] == [0, 0]


def test_whole_images_same_draws_variable_sizes_and_percentile_interpolation(monkeypatch):
    a, b = pair_case()
    # Draw images (one,one), (one,two), (two,two): differences 1, 1/3, -1.
    calls = []
    class Draws:
        def __init__(self, seed):
            assert seed == 5
            self.schedule = iter([0, 0, 0, 1, 1, 1])

        def randrange(self, n):
            calls.append(n)
            return next(self.schedule)

    monkeypatch.setattr("shared.stats.paired.random.Random", Draws)
    result = bootstrap(a, b, seed=5, resamples=3)
    assert calls == [2] * 6  # One schedule for both models; no per-item draws.
    assert (result["items"], result["images"]) == (3, 2)
    assert result["mean_a"] == 2 / 3 and result["mean_b"] == 1 / 3
    assert result["difference"] == 1 / 3  # Unweighted image means would give zero.
    assert result["ci95"] == pytest.approx([-14 / 15, 29 / 30])


def test_constant_difference_and_single_image_degenerate_interval():
    a, b = pair_case()
    for left, right in zip(a["items"], b["items"]):
        left["score"], right["score"] = 0.75, 0.25
        left["cluster"] = right["cluster"] = "only-image"
    result = bootstrap(a, b, seed=0, resamples=20)
    assert result["difference"] == 0.5 and result["ci95"] == [0.5, 0.5]
    assert percentile([1], 0.975) == 1


@pytest.mark.parametrize("mutation", [
    "partial", "disjoint", "empty", "cluster", "cohort", "metric", "version",
    "upstream", "repetitions", "zero_repetitions", "bool_repetitions",
])
def test_rejects_unpaired_inputs(mutation):
    a, b = pair_case()
    if mutation == "partial":
        b["items"].pop()
    elif mutation == "disjoint":
        for item in b["items"]:
            item["key"] += "_different"
    elif mutation == "empty":
        a["items"] = b["items"] = []
    elif mutation == "cluster":
        b["items"][0]["cluster"] = "different"
    else:
        key = "repetitions" if mutation.endswith("repetitions") else mutation
        b[key] = {"repetitions": 2, "zero_repetitions": 0, "bool_repetitions": True}.get(mutation, "different")
    with pytest.raises(ValueError):
        validate_pair(a, b)


@pytest.mark.parametrize("seed,resamples", [(True, 1), (0.1, 1), (0, 0), (0, -1), (0, True), (0, 1.5)])
def test_rejects_invalid_bootstrap_parameters(seed, resamples):
    with pytest.raises(ValueError):
        bootstrap(*pair_case(), seed=seed, resamples=resamples)
