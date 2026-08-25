from __future__ import annotations

from pathlib import Path

import pytest

from shared.multimodal.publish.schema import (
    PublishStatus,
    dataset_item_digest,
    load_model_identity_map,
    make_protocol,
    protocol_fingerprint,
    strongest_status,
    validate_sidecar,
)


REPO = Path(__file__).resolve().parents[3]


def test_protocol_fingerprint_is_canonical_and_model_run_are_not_inputs():
    first = protocol_fingerprint({"split": "test", "limit": None}, {"mode": {"value": "direct"}})
    reordered = protocol_fingerprint({"limit": None, "split": "test"}, {"mode": {"value": "direct"}})
    assert first == reordered


def test_repository_revision_is_informational_but_item_digest_splits_fingerprint():
    first = protocol_fingerprint(
        {"dataset_item_digest": "same-items", "dataset_provenance": {"git_commit": "commit-a"}},
        {},
    )
    other_commit = protocol_fingerprint(
        {"dataset_item_digest": "same-items", "dataset_provenance": {"git_commit": "commit-b"}},
        {},
    )
    other_items = protocol_fingerprint(
        {"dataset_item_digest": "other-items", "dataset_provenance": {"git_commit": "commit-a"}},
        {},
    )
    assert first == other_commit
    assert first != other_items


def test_dataset_item_digest_sorts_then_joins_with_newlines():
    assert dataset_item_digest(["b", "a"]) == dataset_item_digest(["a", "b"])


def test_status_priority_matches_contract():
    assert strongest_status(PublishStatus.NATIVE, PublishStatus.LEGACY_REVALIDATED) is PublishStatus.LEGACY_REVALIDATED
    assert strongest_status(PublishStatus.UNSCORED, PublishStatus.REJECTED) is PublishStatus.REJECTED


def test_publishable_sidecar_cannot_have_critical_unknown():
    sidecar = {
        "schema_version": 1,
        "status": "LEGACY_REVALIDATED",
        "publishable": True,
        "aggregation_allowed": False,
        "protocol": make_protocol({}, {}, ["dataset_item_digest"]),
        "counts": {"attempted": 1, "measured": 1, "errored": 0, "unresolved": 0},
    }
    with pytest.raises(ValueError):
        validate_sidecar(sidecar)


def test_explicit_model_aliases_are_canonical_and_fp8_is_not_merged():
    mapping = load_model_identity_map(REPO)
    assert mapping["gemma_4_26b_a4b_it"] == "gemma_4_26b_a4b_it"
    assert mapping["google_gemma_4_26b_a4b_it"] == "gemma_4_26b_a4b_it"
    assert mapping["google_gemma_4_26B_A4B_it"] == "gemma_4_26b_a4b_it"
    assert mapping["google_gemma_4_31B_it"] == mapping["gemma_4_31b_it"]
    assert mapping["Qwen_Qwen3.6_35B_A3B"] == mapping["qwen3.6-35b-a3b"]
    assert "qwen_qwen3.6_35b_a3b_fp8" not in mapping


def test_model_identity_loader_rejects_fp8_or_size_erasing_alias(tmp_path):
    config = tmp_path / "configs/model_identity.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        '{"qwen_qwen3.5_35b_a3b_fp8": "qwen_qwen3.5_35b_a3b"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="size/quantization markers"):
        load_model_identity_map(tmp_path)

    config.write_text(
        '{"model_27b": "model_35b"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="size/quantization markers"):
        load_model_identity_map(tmp_path)


@pytest.mark.parametrize("quantized", [
    "qwen-35b-4bit", "qwen-35b-int8", "qwen-35b-8bit",
    "qwen-35b-bnb-4bit", "qwen-35b-q4_k_m",
])
def test_model_identity_loader_rejects_extended_quantization_erasure(tmp_path, quantized):
    config = tmp_path / "configs/model_identity.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        '{"' + quantized + '": "qwen-35b"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="size/quantization markers"):
        load_model_identity_map(tmp_path)


def test_unscored_is_only_valid_for_koffvqa_generation():
    base = {
        "schema_version": 1,
        "status": "UNSCORED",
        "publishable": False,
        "aggregation_allowed": False,
        "protocol": make_protocol({}, {}, []),
        "counts": {"attempted": 1, "measured": 1, "errored": 0, "unresolved": 0},
    }
    valid = {**base, "benchmark_id": "KOFFVQA", "variant": "generation"}
    validate_sidecar(valid)
    invalid = {**base, "benchmark_id": "KRETA", "variant": "direct"}
    with pytest.raises(ValueError, match="only valid"):
        validate_sidecar(invalid)


def test_publishable_counts_are_complete_nonnegative_and_ordered():
    sidecar = {
        "schema_version": 1,
        "benchmark_id": "K-DTCBench",
        "status": "NATIVE",
        "publishable": True,
        "aggregation_allowed": False,
        "protocol": make_protocol({}, {}, []),
        "counts": {
            "attempted": 1, "measured": 1, "errored": 0,
            "unresolved": 0, "correct_measured": 1,
        },
        "metrics": {"axes": [{
            "name": "overall", "numerator": 1, "denominator": 1,
            "value": 1.0, "unit": "fraction",
        }]},
    }
    validate_sidecar(sidecar)
    for bad_counts in (
        {},
        {"attempted": 1, "measured": 1, "errored": 0, "unresolved": 0},
        {"attempted": 1, "measured": 1, "errored": 0, "unresolved": 0, "correct_measured": 2},
        {"attempted": 1, "measured": -1, "errored": 1, "unresolved": 1, "correct_measured": 0},
    ):
        invalid = {**sidecar, "counts": bad_counts}
        with pytest.raises(ValueError, match="count"):
            validate_sidecar(invalid)

def test_publishable_accuracy_sidecar_requires_valid_overall_fraction():
    sidecar = {
        "schema_version": 1,
        "benchmark_id": "K-DTCBench",
        "status": "LEGACY_REVALIDATED",
        "publishable": True,
        "aggregation_allowed": False,
        "protocol": make_protocol({}, {}, []),
        "counts": {"attempted": 1, "measured": 1, "errored": 0, "unresolved": 0},
        "metrics": {"axes": [{"name": "category:x", "numerator": 1, "denominator": 1, "value": 1.0, "unit": "fraction"}]},
    }
    with pytest.raises(ValueError, match="overall fraction"):
        validate_sidecar(sidecar)
