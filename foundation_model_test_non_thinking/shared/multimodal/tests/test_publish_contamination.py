from __future__ import annotations

import json
from pathlib import Path

from shared.multimodal.publish.adapters import parse_kreta_response
from shared.multimodal.publish.derive import derive_source, discover_sources


REPO = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).parent / "fixtures" / "known_kreta_contamination.json"

# The uncontaminated KRETA corpus as of the independent-regrade work.  Named,
# not counted: a count moves for a new run and for a lost one alike.
KNOWN_CLEAN_KRETA_SOURCES = {
    "results/Qwen3.5_122B_A10B_GPTQ_Int4/20260720_235721/vision/multimodal/kreta/Qwen3.5_122B_A10B_GPTQ_Int4_direct.jsonl",
    "results/Qwen_Qwen3.6_35B_A3B/20260524_120652/vision/multimodal/kreta/qwen3.6-35b-a3b_direct.jsonl",
    "results/google_gemma_4_26B_A4B_it/20260621_221741/vision/multimodal/kreta/google_gemma_4_26b_a4b_it_direct.jsonl",
    "results/google_gemma_4_31B_it/20260525_152204/vision/multimodal/kreta/google_gemma_4_31B_it_direct.jsonl",
    "results/qwen3.5_27b/20260525_145725/vision/multimodal/kreta/qwen3.5_27b_direct.jsonl",
    "results/qwen_qwen3.5_27b_fp8/20260705_082256/vision/multimodal/kreta/qwen_qwen3.5_27b_fp8_direct.jsonl",
    "results/qwen_qwen3.5_35b_a3b/20260621_233258/vision/multimodal/kreta/qwen_qwen3.5_35b_a3b_direct.jsonl",
    "results/qwen_qwen3.5_35b_a3b_fp8/20260711_003523/vision/multimodal/kreta/qwen_qwen3.5_35b_a3b_fp8_default.jsonl",
    "results/qwen_qwen3.6_27b/20260622_153150/vision/multimodal/kreta/qwen_qwen3.6_27b_direct.jsonl",
    "results/qwen_qwen3.6_27b_fp8/20260704_081047/vision/multimodal/kreta/qwen_qwen3.6_27b_fp8_direct.jsonl",
    "results/qwen_qwen3.6_35b_a3b_fp8/20260702_133909/vision/multimodal/kreta/qwen_qwen3.6_35b_a3b_fp8_default.jsonl",
}


def test_known_contaminated_kreta_sources_are_rejected():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(cases) == 10
    for case in cases:
        source = REPO / case["path"]
        assert source.is_file(), case["path"]
        _, sidecar = derive_source(source, REPO)
        assert sidecar["status"] == "REJECTED"
        assert sidecar["publishable"] is False
        assert sidecar["counts"]["attempted"] == case["attempted"]
        assert sidecar["counts"]["errored"] == case["errored"]
        rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
        poisoned_correct = sum(
            bool(row.get("if_right"))
            for row in rows
            if isinstance(row.get("response"), dict) and row["response"].get("error")
        )
        assert poisoned_correct == case["errored_marked_correct"]


def test_non_error_kreta_sources_survive_independent_response_regrading():
    dirty = {case["path"] for case in json.loads(FIXTURE.read_text(encoding="utf-8"))}
    sources = [path for path in discover_sources(REPO) if path.suffix == ".jsonl"]
    clean = []
    for path in sources:
        if path.relative_to(REPO).as_posix() in dirty:
            continue
        _, candidate = derive_source(path, REPO)
        if candidate["publishable"]:
            clean.append(path)
    # A bare count cannot tell "a new run landed" from "a known-good source
    # silently went missing" — both move the number.  Pin the sources instead:
    # every one of these must still be publishable, and the corpus may grow.
    found = {path.relative_to(REPO).as_posix() for path in clean}
    assert KNOWN_CLEAN_KRETA_SOURCES <= found, sorted(KNOWN_CLEAN_KRETA_SOURCES - found)
    for source in clean:
        _, sidecar = derive_source(source, REPO)
        rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
        parser_choices = [parse_kreta_response(row.get("response")) for row in rows]
        independent_correct = sum(
            choice == str(row.get("answer", "")).strip().upper()
            for choice, row in zip(parser_choices, rows)
        )
        assert sidecar["status"] == "LEGACY_REVALIDATED", source
        assert sidecar["publishable"] is True
        assert sidecar["counts"]["errored"] == 0
        assert sidecar["counts"]["correct_measured"] == independent_correct
        assert sidecar["counts"]["no_answer"] == sum(not choice for choice in parser_choices)
        assert sidecar["upstream_comparison"]["parser_disagreement_rows"] >= 1
