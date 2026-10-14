"""R4 opt-in guard: preserve tests while excluding repository corpus access."""

import pytest

from shared.multimodal.tests._r3_offline import (
    pytest_collection_modifyitems as _exclude_corpus_tests,
    pytest_sessionstart,
    synthetic_legacy_nlu_key,
)


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """Apply R3 exclusions and skip three additional agent corpus readers."""
    _exclude_corpus_tests(config, items)
    corpus_readers = {
        "test_seeded_field_recall_uses_seed_in_moe_artifact_or_skip",
        "test_agent_tracks_report_leaves_taubench_to_its_own_layer",
        "test_agent_tracks_reproducibility_reads_real_artifacts",
    }
    for item in items:
        if item.originalname in corpus_readers:
            item.add_marker(pytest.mark.skip(
                reason="R4: repository data/results access prohibited"
            ))
