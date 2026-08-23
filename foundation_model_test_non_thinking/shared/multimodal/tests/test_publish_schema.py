from __future__ import annotations

import pytest

from shared.multimodal.publish.schema import (
    PublishStatus,
    dataset_item_digest,
    make_protocol,
    protocol_fingerprint,
    strongest_status,
    validate_sidecar,
)


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
