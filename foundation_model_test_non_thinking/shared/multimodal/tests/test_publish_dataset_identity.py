from __future__ import annotations

import json
from pathlib import Path

from shared.multimodal.publish.adapters import adapt_accuracy, adapt_kreta
from shared.multimodal.publish.schema import dataset_item_digest


REPO = Path(__file__).resolve().parents[3]


def test_kreta_same_items_and_mode_share_fingerprint_across_repo_commits():
    first = adapt_kreta(
        REPO
        / "results/Qwen3.5_122B_A10B_GPTQ_Int4/20260720_235721/vision/multimodal/kreta/"
        "Qwen3.5_122B_A10B_GPTQ_Int4_direct.jsonl"
    )
    second = adapt_kreta(
        REPO
        / "results/google_gemma_4_26B_A4B_it/20260621_221741/vision/multimodal/kreta/"
        "google_gemma_4_26b_a4b_it_direct.jsonl"
    )
    first_recorded = first["protocol"]["recorded"]
    second_recorded = second["protocol"]["recorded"]
    assert first_recorded["dataset_item_digest"] == "0cc4ed8281009d38"
    assert first_recorded["dataset_item_digest"] == second_recorded["dataset_item_digest"]
    assert first_recorded["dataset_provenance"]["git_commit"] != second_recorded["dataset_provenance"]["git_commit"]
    assert first["protocol"]["fingerprint"] == second["protocol"]["fingerprint"]


def test_k_dtcbench_different_artifact_item_sets_have_different_digests():
    full = adapt_accuracy(
        REPO / "results/qwen3.5_27b/20260525_145725/vision/multimodal/k_dtcbench",
        "k_dtcbench",
    )
    truncated = adapt_accuracy(
        REPO / "results/gemma_4_26b_a4b_it/20260503_120057/vision/multimodal/k_dtcbench",
        "k_dtcbench",
    )
    assert full["counts"]["attempted"] == 240
    assert truncated["counts"]["attempted"] == 5
    assert full["protocol"]["recorded"]["dataset_item_digest"] != truncated["protocol"]["recorded"]["dataset_item_digest"]
    assert full["protocol"]["fingerprint"] != truncated["protocol"]["fingerprint"]


def test_mtvqa_dataset_identity_uses_all_row_and_qa_pairs():
    source = REPO / "results/qwen3.5_27b/20260525_145725/vision/multimodal/mtvqa_kr"
    rows = json.loads((source / "results.json").read_text(encoding="utf-8"))
    pairs = [f"{row['row_idx']}\t{row['qa_idx']}" for row in rows]
    sidecar = adapt_accuracy(source, "mtvqa_kr")
    assert len(rows) == len(set(pairs)) == 558
    assert len({row["id"] for row in rows}) == 250
    assert sidecar["protocol"]["recorded"]["dataset_item_digest"] == dataset_item_digest(pairs)
